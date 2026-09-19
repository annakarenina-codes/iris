"""Start the actual IRIS backend with its local TRACE workspace enabled."""

import argparse
import os

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="IRIS calibration backend with request tabs"
    )
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--artifacts",
        action="store_true",
        help="Save controlled inputs/images and dependency responses for replay",
    )
    args = parser.parse_args()
    os.environ["IRIS_TRACE_ENABLED"] = "true"
    if args.artifacts:
        os.environ["IRIS_TRACE_ARTIFACTS"] = "true"
    from app import app

    if args.host not in {"127.0.0.1", "localhost", "::1"} and not app.config.get(
        "IRIS_TRACE_TOKEN"
    ):
        parser.error("Set IRIS_TRACE_TOKEN before listening beyond loopback.")
    print(f"IRIS TRACE: http://{args.host}:{args.port}/debug/trace")
    app.run(
        host=args.host, port=args.port, threaded=True, debug=False, use_reloader=False
    )
