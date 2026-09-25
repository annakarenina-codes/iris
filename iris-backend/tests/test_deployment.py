"""What changes when IRIS stops being a laptop process and becomes an address on the internet."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.safe_fetch import UnsafeImageURL, check_public_url, get_public_url


def resolving_to(*addresses):
    """Stands in for DNS, so a test does not depend on what a name resolves to today."""
    return lambda host, *_args, **_kwargs: [
        (2, 1, 6, "", (address, 0)) for address in addresses
    ]


class HealthTests(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app
        self.client = app.app.test_client()

    def test_health_answers_without_loading_a_model(self):
        with patch("pipeline.verdict_generator.get_model") as model:
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")
        model.assert_not_called()


class AccessTokenTests(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app
        self.client = app.app.test_client()

    def test_no_token_configured_leaves_the_endpoints_as_they_were(self):
        with patch.object(self.app, "API_TOKEN", ""):
            with patch.object(self.app, "verify_text_payload", return_value={"verdict": "Not Found"}):
                response = self.client.post("/verify", json={"text": "Marcos signed the budget."})

        self.assertEqual(response.status_code, 200)

    def test_a_configured_token_turns_anonymous_callers_away(self):
        with patch.object(self.app, "API_TOKEN", "a-shared-secret"):
            response = self.client.post("/verify", json={"text": "Marcos signed the budget."})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "unauthorized")

    def test_the_right_token_is_let_through_either_way_it_is_sent(self):
        headers = [
            {"X-IRIS-Token": "a-shared-secret"},
            {"Authorization": "Bearer a-shared-secret"},
        ]

        for header in headers:
            with self.subTest(header=next(iter(header))):
                with patch.object(self.app, "API_TOKEN", "a-shared-secret"):
                    with patch.object(self.app, "verify_text_payload",
                                      return_value={"verdict": "Not Found"}):
                        response = self.client.post(
                            "/verify", json={"text": "Marcos signed the budget."}, headers=header)

                self.assertEqual(response.status_code, 200)

    def test_a_wrong_token_is_turned_away(self):
        with patch.object(self.app, "API_TOKEN", "a-shared-secret"):
            response = self.client.post("/verify", json={"text": "A claim."},
                                        headers={"X-IRIS-Token": "not-the-secret"})

        self.assertEqual(response.status_code, 401)

    def test_the_image_endpoint_is_covered_too(self):
        with patch.object(self.app, "API_TOKEN", "a-shared-secret"):
            response = self.client.post("/verify-image", json={"image_url": "https://example.org/a.png"})

        self.assertEqual(response.status_code, 401)

    def test_the_health_check_is_not_asked_for_a_token(self):
        with patch.object(self.app, "API_TOKEN", "a-shared-secret"):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)


class SubmittedImageURLTests(unittest.TestCase):
    """A URL the caller chooses is fetched by the server, from wherever the server sits."""

    def test_public_addresses_are_allowed(self):
        with patch("socket.getaddrinfo", resolving_to("93.184.216.34")):
            parsed = check_public_url("https://example.org/photo.jpg")

        self.assertEqual(parsed.hostname, "example.org")

    def test_the_hosts_own_metadata_service_is_refused(self):
        with patch("socket.getaddrinfo", resolving_to("169.254.169.254")):
            with self.assertRaises(UnsafeImageURL):
                check_public_url("http://metadata.internal/latest/meta-data/")

    def test_private_and_loopback_addresses_are_refused(self):
        for address in ["127.0.0.1", "10.0.0.5", "192.168.1.10", "172.16.0.9", "::1", "fd00::1"]:
            with self.subTest(address=address):
                with patch("socket.getaddrinfo", resolving_to(address)):
                    with self.assertRaises(UnsafeImageURL):
                        check_public_url("http://wherever.example/photo.jpg")

    def test_a_private_address_dressed_as_ipv6_is_still_private(self):
        with patch("socket.getaddrinfo", resolving_to("::ffff:127.0.0.1")):
            with self.assertRaises(UnsafeImageURL):
                check_public_url("http://wherever.example/photo.jpg")

    def test_a_name_with_one_public_and_one_private_answer_is_refused(self):
        with patch("socket.getaddrinfo", resolving_to("93.184.216.34", "127.0.0.1")):
            with self.assertRaises(UnsafeImageURL):
                check_public_url("http://wherever.example/photo.jpg")

    def test_schemes_other_than_http_are_refused(self):
        for url in ["file:///etc/passwd", "gopher://example.org/", "ftp://example.org/a.png"]:
            with self.subTest(url=url):
                with self.assertRaises(UnsafeImageURL):
                    check_public_url(url)

    def test_a_public_page_cannot_redirect_the_fetch_somewhere_private(self):
        """The whole point of checking each hop: hop one is public, hop two is not."""
        redirect = type("Response", (), {
            "status_code": 302,
            "headers": {"Location": "http://169.254.169.254/latest/meta-data/"},
            "close": lambda self: None,
        })()

        answers = {"example.org": ["93.184.216.34"], "169.254.169.254": ["169.254.169.254"]}

        def resolve(host, *_args, **_kwargs):
            return [(2, 1, 6, "", (address, 0)) for address in answers[host]]

        with patch("socket.getaddrinfo", side_effect=resolve):
            with patch("pipeline.safe_fetch.requests.get", return_value=redirect):
                with self.assertRaises(UnsafeImageURL):
                    get_public_url("https://example.org/photo.jpg")


class ProductionEntryTests(unittest.TestCase):
    def test_the_werkzeug_debugger_is_no_longer_switched_on_in_the_source(self):
        """
        Debug mode runs whatever a caller sends the debugger. It has to be asked for now,
        and gunicorn imports the app rather than going through this branch at all.
        """
        source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

        self.assertNotIn("app.run(debug=True)", source)
        self.assertIn('debug=os.getenv("FLASK_DEBUG"', source)




class RequestSizeTests(unittest.TestCase):
    def test_an_oversized_body_is_refused_before_it_is_read(self):
        import app

        self.assertEqual(app.app.config["MAX_CONTENT_LENGTH"], 16 * 1024 * 1024)

        client = app.app.test_client()
        response = client.post(
            "/verify",
            data=b"x" * (17 * 1024 * 1024),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
