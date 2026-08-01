import React, { useEffect, useId, useRef, useState } from "react";

const CLAIM =
  "Number 1 parin si Duterte sa Survey! Kahit anong paninira nila, panalo parin tayo!";

const OCR_CLAIM =
  "Viral post claims a candidate has already been declared the winner of the 2028 presidential survey.";

const STORAGE_KEYS = {
  theme: "iris-extension-theme",
  fontSize: "iris-extension-font-size",
};

const FONT_OPTIONS = [
  { value: "small", label: "Small", scale: 0.9 },
  { value: "default", label: "Default", scale: 1 },
  { value: "large", label: "Large", scale: 1.15 },
  { value: "xl", label: "XL", scale: 1.3 },
];

const TEXT_RESULT = {
  total_claims: 3,
  claims: [
    {
      claim_id: 1,
      claim_text: CLAIM,
      politically_sensitive: true,
      corroboration: { count: 2, total: 6 },
      verdict: {
        icon: "⚠️",
        label: "Partially Matched",
        color: "#78350F",
        bg: "#FFFBEB",
        border: "#FCD34D",
        explanation:
          'Survey coverage was found, but the "Number 1" ranking is not directly confirmed by the related reports.',
      },
      sources: [
        {
          outlet: "Philippine Daily Inquirer",
          date: "May 3, 2025",
          title: "VP Sara Duterte leads Pulse Asia nationwide survey",
        },
        {
          outlet: "GMA Network",
          date: "Apr 28, 2025",
          title: "SWS: Duterte retains support base despite legal woes",
        },
      ],
    },
    {
      claim_id: 2,
      claim_text:
        "The latest survey proves where the support really is.",
      politically_sensitive: true,
      corroboration: { count: 3, total: 6 },
      verdict: {
        icon: "✅",
        label: "Verified",
        color: "#065F46",
        bg: "#ECFDF5",
        border: "#6EE7B7",
        explanation:
          "Multiple reports confirm that recent polling data measured voter support for the named political figure.",
      },
      sources: [
        {
          outlet: "Philstar.com",
          date: "May 2, 2025",
          title: "Latest nationwide poll tracks support for 2028 hopefuls",
        },
        {
          outlet: "Manila Bulletin",
          date: "May 1, 2025",
          title: "Pollster releases new national voter preference survey",
        },
      ],
    },
    {
      claim_id: 3,
      claim_text:
        "Public support remains strong despite recent legal controversy.",
      politically_sensitive: true,
      corroboration: { count: 1, total: 6 },
      verdict: {
        icon: "❓",
        label: "Not Found",
        color: "#374151",
        bg: "#F9FAFB",
        border: "#D1D5DB",
        explanation:
          "IRIS found related political coverage, but no source directly confirms this specific support claim.",
      },
      sources: [
        {
          outlet: "VERA Files",
          date: "Apr 30, 2025",
          title: "Explainer: How to read political survey claims online",
        },
      ],
    },
  ],
  ignored_segments: [
    { reason: "opinion", count: 1, label: "opinion" },
    { reason: "forecast_or_projection", count: 1, label: "prediction" },
  ],
};

const PHOTO_RESULT = {
  total_claims: 1,
  claims: [
    {
      claim_id: 1,
      claim_text: OCR_CLAIM,
      politically_sensitive: true,
      corroboration: { count: 1, total: 6 },
      verdict: {
        icon: "⚠️",
        label: "Partially Matched",
        color: "#78350F",
        bg: "#FFFBEB",
        border: "#FCD34D",
        explanation:
          "IRIS found political survey coverage, but no source confirms that a 2028 winner has already been declared.",
      },
      sources: [
        {
          outlet: "VERA Files",
          date: "May 4, 2025",
          title: "Fact check: No winner has been declared for the 2028 election",
        },
      ],
    },
  ],
  ignored_segments: [],
};

const FAQ_ITEMS = [
  {
    question: "What does IRIS check?",
    answer:
      "IRIS checks selected claims against trusted Philippine news sources and fact-checking references.",
  },
  {
    question: 'What does "Not Found" mean?',
    answer:
      "It means IRIS did not find a direct source match for the selected claim. It is not the same as false.",
  },
  {
    question: "What data is collected?",
    answer:
      "Only the selected text or uploaded image text is used for the check. The mockup does not keep scan history.",
  },
  {
    question: "Who supports the fact checks?",
    answer:
      "IRIS surfaces related reporting and fact-checking references, including VERA Files where available.",
  },
];

function safeStorageRead(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeStorageWrite(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage can be unavailable in some extension preview contexts.
  }
}

function getInitialTheme() {
  const saved = safeStorageRead(STORAGE_KEYS.theme);
  if (saved === "light" || saved === "dark") return saved;

  return "light";
}

function getInitialFontSize() {
  const saved = safeStorageRead(STORAGE_KEYS.fontSize);
  return FONT_OPTIONS.some((option) => option.value === saved)
    ? saved
    : "default";
}

function IrisEye({ size = 28, monochrome = false }) {
  const gradientId = useId();
  const fill = monochrome ? "currentColor" : `url(#${gradientId})`;

  return (
    <svg
      className="iris-eye"
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient
          id={gradientId}
          x1="0"
          y1="100"
          x2="100"
          y2="0"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#6D28D9" />
          <stop offset="0.5" stopColor="#8B5CF6" />
          <stop offset="1" stopColor="#C084FC" />
        </linearGradient>
      </defs>
      <ellipse cx="44" cy="46" rx="30" ry="18" fill={fill} />
      <circle
        cx="50"
        cy="48"
        r="20"
        fill={monochrome ? "none" : "white"}
        opacity={monochrome ? 1 : 0.9}
        stroke={monochrome ? "currentColor" : "none"}
        strokeWidth={monochrome ? 4 : 0}
      />
      <circle cx="50" cy="48" r="11" fill={fill} />
      <circle cx="44" cy="43" r="4" fill="white" opacity="0.7" />
      <line
        x1="64"
        y1="62"
        x2="78"
        y2="76"
        stroke={fill}
        strokeWidth="8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M10.8 18a7.2 7.2 0 1 1 5.1-2.1L20 20"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.1"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ExternalLinkIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M6 3h7v7M13 3 6.5 9.5M12 12.5H3.5v-9H8"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ImageIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 18 18" aria-hidden="true">
      <rect
        x="2.75"
        y="3.25"
        width="12.5"
        height="11.5"
        rx="2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <path
        d="m3 12 3.1-3.1 3.4 3.3 1.8-1.8 3.7 3.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="12.4" cy="6.4" r="1.15" fill="currentColor" />
    </svg>
  );
}

function GearIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 8.2a3.8 3.8 0 1 1 0 7.6 3.8 3.8 0 0 1 0-7.6Zm7.2 4.1c.03-.2.03-.4.03-.6s0-.4-.03-.6l2-1.5-2-3.5-2.4 1a8 8 0 0 0-1-.6L15.5 4h-4l-.4 2.5c-.34.16-.68.36-1 .6l-2.3-1-2 3.5 2 1.5c-.04.2-.04.4-.04.6s0 .4.04.6l-2 1.5 2 3.5 2.3-1c.32.24.66.44 1 .6l.4 2.5h4l.4-2.5c.34-.16.68-.36 1-.6l2.4 1 2-3.5-2.1-1.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function QuestionIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
      <circle
        cx="12"
        cy="12"
        r="8.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      />
      <path
        d="M9.8 9.5a2.4 2.4 0 0 1 4.7.6c0 1.9-2.4 2-2.4 3.8M12 17h.01"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
      />
    </svg>
  );
}

function ChevronLeftIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true">
      <path
        d="m11 4-5 5 5 5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true">
      <path
        d="m7 4 5 5-5 5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path
        d="M3.2 3.2 10.8 10.8M10.8 3.2 3.2 10.8"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MinusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path
        d="M3 7h8"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function Dots() {
  return (
    <div className="scan-dots" aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
  );
}

function truncateClaim(text) {
  return text.length > 300 ? `${text.slice(0, 297)}...` : text;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

function formatSkippedSegments(segments) {
  return segments
    .map((segment) => `${segment.count} ${segment.label}`)
    .join(", ");
}

function SourceCard({ outlet, date, title }) {
  return (
    <button className="source-card" type="button">
      <span className="source-card__meta">
        <span>{outlet}</span>
        <time>{date}</time>
      </span>
      <span className="source-card__title">{title}</span>
      <span className="source-card__link">
        <ExternalLinkIcon />
        Read full article
      </span>
    </button>
  );
}

function ClaimNavigator({ claimIndex, totalClaims, onPrevClaim, onNextClaim }) {
  if (totalClaims <= 1) return null;

  return (
    <div className="claim-navigator" aria-label="Claim navigation">
      <button
        className="claim-navigator__button"
        type="button"
        aria-label="Previous claim"
        disabled={claimIndex === 0}
        onClick={onPrevClaim}
      >
        <ChevronLeftIcon />
      </button>
      <strong>
        Claim {claimIndex + 1} of {totalClaims}
      </strong>
      <button
        className="claim-navigator__button"
        type="button"
        aria-label="Next claim"
        disabled={claimIndex === totalClaims - 1}
        onClick={onNextClaim}
      >
        <ChevronRightIcon />
      </button>
    </div>
  );
}

function SkippedSegmentsNote({ segments }) {
  if (!segments.length) return null;

  return (
    <div className="skipped-note">
      <span aria-hidden="true">i</span>
      <p>
        {segments.length} other parts of this post were not checked (
        {formatSkippedSegments(segments)}).
      </p>
    </div>
  );
}

function ResultClaimBlock({ claim, claimMode }) {
  return (
    <>
      <div className="result-claim">
        {claimMode === "photo" && <span>Text extracted from image</span>}
        <blockquote>{truncateClaim(claim.claim_text)}</blockquote>
      </div>

      {claim.politically_sensitive && (
        <div className="political-flag">
          <span aria-hidden="true">!</span>
          <div>
            <strong>Politically Sensitive</strong>
            <p>Apply extra scrutiny before sharing.</p>
          </div>
        </div>
      )}

      <div
        className="verdict-card"
        style={{
          background: claim.verdict.bg,
          borderColor: claim.verdict.border,
          color: claim.verdict.color,
        }}
      >
        <span className="verdict-card__icon">{claim.verdict.icon}</span>
        <div>
          <strong>{claim.verdict.label}</strong>
          <p>{claim.verdict.explanation}</p>
        </div>
      </div>

      <div className="corroboration-row">
        <strong>
          {claim.corroboration.count} of {claim.corroboration.total}
        </strong>
        <span>sources returned related articles</span>
      </div>

      <div className="related-label">Related Articles</div>
      <div className="source-list">
        {claim.sources.length > 0 ? (
          claim.sources.map((source) => (
            <SourceCard key={`${source.outlet}-${source.date}-${source.title}`} {...source} />
          ))
        ) : (
          <div className="source-empty">No direct article match found.</div>
        )}
      </div>
    </>
  );
}

function SettingsPanel({
  theme,
  fontSize,
  onThemeChange,
  onFontSizeChange,
  onCloseSettings,
}) {
  return (
    <section className="iris-state iris-settings">
      <div className="settings-title">
        <h2>Settings</h2>
        <button className="iris-button iris-button--secondary settings-done" type="button" onClick={onCloseSettings}>
          Done
        </button>
      </div>

      <div className="setting-row">
        <div>
          <strong>Night mode</strong>
          <span>IRIS panel only</span>
        </div>
        <button
          className={`switch-button ${theme === "dark" ? "is-on" : ""}`}
          type="button"
          role="switch"
          aria-checked={theme === "dark"}
          aria-label="Toggle night mode"
          onClick={() => onThemeChange(theme === "dark" ? "light" : "dark")}
        >
          <span />
        </button>
      </div>

      <div className="setting-block">
        <strong>Font size</strong>
        <div className="font-options" role="group" aria-label="Font size">
          {FONT_OPTIONS.map((option) => (
            <button
              className={fontSize === option.value ? "is-active" : ""}
              key={option.value}
              type="button"
              onClick={() => onFontSizeChange(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function FaqOverlay({ onCloseFaq }) {
  return (
    <div className="faq-overlay" onClick={onCloseFaq}>
      <section
        className="faq-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="faq-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header>
          <h2 id="faq-title">FAQ</h2>
          <button
            className="iris-icon-button iris-icon-button--plain"
            type="button"
            aria-label="Close FAQ"
            onClick={onCloseFaq}
          >
            <CloseIcon />
          </button>
        </header>
        <div className="faq-list">
          {FAQ_ITEMS.map((item) => (
            <article key={item.question}>
              <h3>{item.question}</h3>
              <p>{item.answer}</p>
            </article>
          ))}
          <a href="https://verafiles.org" target="_blank" rel="noreferrer">
            Open VERA Files
          </a>
        </div>
      </section>
    </div>
  );
}

function IrisWidget({
  status,
  selectedText,
  claimMode,
  collapsed,
  theme,
  fontSize,
  verification,
  claimIndex,
  faqOpen,
  onCollapse,
  onExpand,
  onBubblePointerDown,
  onBubblePointerMove,
  onBubblePointerUp,
  onCheck,
  onUploadPhoto,
  onCancelPhoto,
  onReset,
  onPrevClaim,
  onNextClaim,
  onOpenSettings,
  onCloseSettings,
  onOpenFaq,
  onCloseFaq,
  onThemeChange,
  onFontSizeChange,
  bubbleDragging,
}) {
  const detected =
    status === "detected" ||
    status === "photo" ||
    status === "scanning" ||
    status === "result";
  const scanning = status === "scanning";
  const totalClaims = verification.claims.length;
  const activeClaim = verification.claims[Math.min(claimIndex, totalClaims - 1)];
  const activeFontScale =
    FONT_OPTIONS.find((option) => option.value === fontSize)?.scale ?? 1;
  const shellStyle = { "--iris-scale": activeFontScale };

  if (collapsed) {
    return (
      <button
        className={`iris-pill iris-extension-shell ${bubbleDragging ? "is-dragging" : ""}`}
        type="button"
        aria-label="Open IRIS panel"
        data-theme={theme}
        style={shellStyle}
        onPointerDown={onBubblePointerDown}
        onPointerMove={onBubblePointerMove}
        onPointerUp={onBubblePointerUp}
        onPointerCancel={onBubblePointerUp}
        onClick={onExpand}
      >
        <IrisEye size={22} />
        <span>IRIS</span>
        <i
          className={`iris-pill__status ${
            scanning ? "is-scanning" : detected ? "is-ready" : ""
          }`}
          aria-hidden="true"
        />
      </button>
    );
  }

  return (
    <aside
      className={`iris-panel iris-extension-shell ${bubbleDragging ? "is-dragging" : ""}`}
      data-theme={theme}
      style={shellStyle}
      aria-label="IRIS fact-check panel"
    >
      <header
        className="iris-panel__header"
        onPointerDown={onBubblePointerDown}
        onPointerMove={onBubblePointerMove}
        onPointerUp={onBubblePointerUp}
        onPointerCancel={onBubblePointerUp}
      >
        <div className="iris-panel__brand">
          <IrisEye size={28} />
          <div>
            <strong>IRIS</strong>
            <span>INTELLIGENT REAL-TIME INFORMATION SCANNER</span>
          </div>
        </div>
        <button
          className="iris-icon-button"
          type="button"
          aria-label="Collapse IRIS panel"
          onClick={onCollapse}
        >
          <MinusIcon />
        </button>
      </header>

      <div className="iris-panel__body">
        {status === "idle" && (
          <section className="iris-state iris-state--idle">
            <div className="idle-search">
              <SearchIcon />
            </div>
            <h2>Ready to fact-check</h2>
            <p>
              Highlight a news claim on this page, then use IRIS to verify it
              against Philippine sources.
            </p>
            <div className="empty-claim">
              <span>No text selected yet.</span>
              <strong>Select text to begin</strong>
            </div>
            <button className="iris-button iris-button--disabled" type="button" disabled>
              Check with IRIS
            </button>
            <button className="iris-button iris-button--upload" type="button" onClick={onUploadPhoto}>
              <ImageIcon />
              Upload photo
            </button>
          </section>
        )}

        {status === "photo" && (
          <section className="iris-state iris-state--photo">
            <div className="photo-preview">
              <span>campaign-card.jpg</span>
              <p>{OCR_CLAIM}</p>
            </div>
            <div className="ocr-preview">
              <span>Detected text preview</span>
              <blockquote>{OCR_CLAIM}</blockquote>
            </div>
            <button className="iris-button iris-button--primary" type="button" onClick={() => onCheck("photo")}>
              <IrisEye size={18} monochrome />
              Scan image text
            </button>
            <button className="iris-button iris-button--secondary photo-cancel" type="button" onClick={onCancelPhoto}>
              Cancel
            </button>
          </section>
        )}

        {status === "detected" && (
          <section className="iris-state">
            <div className="detected-row">
              <span aria-hidden="true" />
              <strong>Text detected</strong>
            </div>
            <blockquote>{truncateClaim(selectedText)}</blockquote>
            <p className="supporting-note">
              IRIS will check this claim against 6 credible Philippine news
              sources and VERA Files.
            </p>
            <button className="iris-button iris-button--primary" type="button" onClick={() => onCheck()}>
              <IrisEye size={18} monochrome />
              Check with IRIS
            </button>
          </section>
        )}

        {status === "scanning" && (
          <section className="iris-state iris-state--scanning">
            <blockquote>{truncateClaim(selectedText)}</blockquote>
            <Dots />
            <h2>Scanning sources...</h2>
            <p>
              Checking GMA, Inquirer, PhilStar, Manila Bulletin, PNA, PIA, and
              VERA Files.
            </p>
            <div className="progress-track" aria-hidden="true">
              <span />
            </div>
          </section>
        )}

        {status === "result" && (
          <section className="iris-state iris-state--result">
            <ClaimNavigator
              claimIndex={claimIndex}
              totalClaims={totalClaims}
              onPrevClaim={onPrevClaim}
              onNextClaim={onNextClaim}
            />

            <div className="claim-result-block" key={activeClaim.claim_id}>
              <ResultClaimBlock claim={activeClaim} claimMode={claimMode} />
              {claimIndex === totalClaims - 1 && (
                <SkippedSegmentsNote segments={verification.ignored_segments} />
              )}
            </div>

            <p className="disclaimer">
              IRIS is an assistant, not an authority. Always read the linked
              articles before sharing.
            </p>

            <button className="iris-button iris-button--secondary" type="button" onClick={onReset}>
              Check another claim
            </button>
          </section>
        )}

        {status === "settings" && (
          <SettingsPanel
            theme={theme}
            fontSize={fontSize}
            onThemeChange={onThemeChange}
            onFontSizeChange={onFontSizeChange}
            onCloseSettings={onCloseSettings}
          />
        )}
      </div>

      <footer className="iris-panel__footer">
        <button
          className={status === "settings" ? "is-active" : ""}
          type="button"
          aria-label="Open IRIS settings"
          onClick={onOpenSettings}
        >
          <GearIcon />
        </button>
        <button type="button" aria-label="Open IRIS FAQ" onClick={onOpenFaq}>
          <QuestionIcon />
        </button>
      </footer>

      {faqOpen && <FaqOverlay onCloseFaq={onCloseFaq} />}
    </aside>
  );
}

function ChromeTopBar() {
  return (
    <div className="chrome">
      <div className="chrome__tabs">
        <div className="chrome__window-controls" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div className="chrome__tab is-active">
          <span className="fb-dot">f</span>
          <span>Facebook</span>
        </div>
        <div className="chrome__tab">New Tab</div>
      </div>
      <div className="chrome__toolbar">
        <div className="chrome__nav" aria-hidden="true">
          <button type="button">{"<"}</button>
          <button type="button">{">"}</button>
          <button type="button">R</button>
        </div>
        <div className="chrome__address">
          <span className="lock-icon" />
          <span>https://www.facebook.com</span>
        </div>
        <div className="chrome__actions">
          <button type="button" aria-label="Bookmark">
            *
          </button>
          <button className="toolbar-iris" type="button" aria-label="IRIS extension active">
            <IrisEye size={18} />
          </button>
          <button type="button" aria-label="Chrome menu">
            ...
          </button>
        </div>
      </div>
    </div>
  );
}

function FacebookHeader() {
  return (
    <header className="facebook-header">
      <div className="facebook-header__left">
        <div className="facebook-logo">f</div>
        <div className="facebook-search">
          <SearchIcon />
          <span>Search Facebook</span>
        </div>
      </div>
      <nav className="facebook-header__nav" aria-label="Facebook sections">
        <button className="is-active" type="button">
          Home
        </button>
        <button type="button">Watch</button>
        <button type="button">Groups</button>
        <button type="button">Gaming</button>
      </nav>
      <div className="facebook-header__right">
        <button type="button">Menu</button>
        <button type="button">Messenger</button>
        <button type="button">Alerts</button>
      </div>
    </header>
  );
}

function Sidebar() {
  const items = ["Kiko Barzaga", "Friends", "Groups", "Memories", "Saved", "Feeds"];

  return (
    <aside className="facebook-sidebar" aria-label="Facebook sidebar">
      {items.map((item, index) => (
        <button key={item} type="button">
          <span>{index === 0 ? "KB" : item.slice(0, 1)}</span>
          {item}
        </button>
      ))}
    </aside>
  );
}

function Contacts() {
  return (
    <aside className="facebook-contacts" aria-label="Contacts">
      <div className="contacts-card">
        <h3>Sponsored</h3>
        <div className="sponsored-item">
          <div />
          <span>Campus news monitoring tools for student researchers</span>
        </div>
      </div>
      <div className="contacts-card">
        <h3>Contacts</h3>
        {["Alyssa M.", "Renz T.", "Miguel C.", "Jana P."].map((name) => (
          <button key={name} type="button">
            <span>{name.slice(0, 1)}</span>
            {name}
          </button>
        ))}
      </div>
    </aside>
  );
}

function Composer() {
  return (
    <section className="composer" aria-label="Create post">
      <div className="composer__top">
        <div className="profile-token">KB</div>
        <button type="button">What is on your mind?</button>
      </div>
      <div className="composer__actions">
        <button type="button">Live video</button>
        <button type="button">Photo/video</button>
        <button type="button">Feeling/activity</button>
      </div>
    </section>
  );
}

function FacebookPost({ highlighted, onContextMenu, onClaimSelect }) {
  return (
    <article className="fb-post" onContextMenu={onContextMenu}>
      <header className="fb-post__header">
        <div className="profile-token profile-token--red">KB</div>
        <div>
          <div className="fb-post__author">
            Congressman Kiko Barzaga
            <span className="verified-dot" aria-label="Verified page" />
          </div>
          <div className="fb-post__meta">7h - Public</div>
        </div>
        <button type="button" aria-label="Post options">
          ...
        </button>
      </header>

      <div className="fb-post__caption">
        Sharing this because people deserve to know the truth. The latest
        survey proves where the support really is.
      </div>

      <div
        className={`claim-graphic ${highlighted ? "is-highlighted" : ""}`}
        onDoubleClick={onClaimSelect}
      >
        <div className="claim-graphic__photo" />
        <div className="claim-graphic__overlay">
          <p className="post-claim">{CLAIM}</p>
          <span>#Duterte2028</span>
        </div>
      </div>

      <div className="fb-post__counts">
        <span>14K reactions</span>
        <span>2.8K comments - 3.1K shares</span>
      </div>
      <div className="fb-post__actions">
        <button type="button">Like</button>
        <button type="button">Comment</button>
        <button type="button">Share</button>
      </div>
    </article>
  );
}

function NativeContextMenu({ menu, onCheck, onUploadPhoto, onClose }) {
  useEffect(() => {
    if (!menu) return undefined;
    const close = () => onClose();
    window.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [menu, onClose]);

  if (!menu) return null;

  return (
    <div
      className="native-menu iris-extension-shell"
      style={{ left: menu.x, top: menu.y }}
      role="menu"
    >
      <button type="button" role="menuitem" onClick={() => onCheck()}>
        <IrisEye size={16} />
        Check with IRIS
      </button>
      <button type="button" role="menuitem" onClick={onUploadPhoto}>
        <ImageIcon />
        Check image with IRIS
      </button>
    </div>
  );
}

function FacebookPage({ hasSelection, onContextMenu, onClaimSelect }) {
  return (
    <main className="facebook-page">
      <FacebookHeader />
      <div className="facebook-layout">
        <Sidebar />
        <section className="feed-column" aria-label="Facebook feed">
          <Composer />
          <FacebookPost
            highlighted={hasSelection}
            onContextMenu={onContextMenu}
            onClaimSelect={onClaimSelect}
          />
          <article className="fb-post fb-post--skeleton" aria-hidden="true">
            <div />
            <span />
            <span />
            <section />
          </article>
        </section>
        <Contacts />
      </div>
    </main>
  );
}

function getCleanSelection() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return "";

  const anchor = selection.anchorNode;
  const focus = selection.focusNode;
  const irisShell = document.querySelector(".iris-extension-shell");

  if (
    irisShell &&
    ((anchor && irisShell.contains(anchor)) || (focus && irisShell.contains(focus)))
  ) {
    return "";
  }

  return selection.toString().replace(/\s+/g, " ").trim();
}

export default function App() {
  const [selectedText, setSelectedText] = useState("");
  const [claimMode, setClaimMode] = useState("text");
  const [status, setStatus] = useState("idle");
  const [settingsReturnStatus, setSettingsReturnStatus] = useState("idle");
  const [collapsed, setCollapsed] = useState(false);
  const [menu, setMenu] = useState(null);
  const [verification, setVerification] = useState(TEXT_RESULT);
  const [claimIndex, setClaimIndex] = useState(0);
  const [theme, setTheme] = useState(getInitialTheme);
  const [fontSize, setFontSize] = useState(getInitialFontSize);
  const [faqOpen, setFaqOpen] = useState(false);
  const [bubblePosition, setBubblePosition] = useState(null);
  const [bubbleDragging, setBubbleDragging] = useState(false);
  const timerRef = useRef(null);
  const dragRef = useRef(null);
  const suppressBubbleClickRef = useRef(false);

  useEffect(() => {
    safeStorageWrite(STORAGE_KEYS.theme, theme);
  }, [theme]);

  useEffect(() => {
    safeStorageWrite(STORAGE_KEYS.fontSize, fontSize);
  }, [fontSize]);

  useEffect(() => {
    const updateSelection = () => {
      const text = getCleanSelection();
      if (text.length > 8) {
        setSelectedText(text);
        setClaimMode("text");
        setStatus((current) =>
          current === "scanning" || current === "result" || current === "settings"
            ? current
            : "detected"
        );
      }
    };

    document.addEventListener("selectionchange", updateSelection);
    window.addEventListener("mouseup", updateSelection);
    window.addEventListener("keyup", updateSelection);

    return () => {
      document.removeEventListener("selectionchange", updateSelection);
      window.removeEventListener("mouseup", updateSelection);
      window.removeEventListener("keyup", updateSelection);
    };
  }, []);

  useEffect(() => {
    return () => clearTimeout(timerRef.current);
  }, []);

  const beginCheck = (mode = claimMode) => {
    const nextMode = mode === "photo" ? "photo" : "text";
    const text = nextMode === "photo" ? OCR_CLAIM : selectedText || CLAIM;

    setMenu(null);
    setFaqOpen(false);
    setSelectedText(text);
    setClaimMode(nextMode);
    setVerification(nextMode === "photo" ? PHOTO_RESULT : TEXT_RESULT);
    setClaimIndex(0);
    setCollapsed(false);
    setStatus("scanning");
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setStatus((current) => (current === "settings" ? "settings" : "result"));
      setSettingsReturnStatus((current) =>
        current === "scanning" ? "result" : current
      );
    }, 1800);
  };

  const reset = () => {
    clearTimeout(timerRef.current);
    setSelectedText("");
    setClaimMode("text");
    setVerification(TEXT_RESULT);
    setClaimIndex(0);
    setStatus("idle");
    setSettingsReturnStatus("idle");
    setMenu(null);
    setFaqOpen(false);
    window.getSelection()?.removeAllRanges();
  };

  const handleContextMenu = (event) => {
    const text = getCleanSelection();
    if (!text) return;

    event.preventDefault();
    setSelectedText(text);
    setClaimMode("text");
    setVerification(TEXT_RESULT);
    setClaimIndex(0);
    setStatus((current) => (current === "result" ? current : "detected"));
    setMenu({ x: event.clientX, y: event.clientY });
  };

  const selectClaim = () => {
    setSelectedText(CLAIM);
    setClaimMode("text");
    setVerification(TEXT_RESULT);
    setClaimIndex(0);
    setStatus((current) =>
      current === "scanning" || current === "result" || current === "settings"
        ? current
        : "detected"
    );
  };

  const uploadPhoto = () => {
    setMenu(null);
    setFaqOpen(false);
    setCollapsed(false);
    setSelectedText(OCR_CLAIM);
    setClaimMode("photo");
    setVerification(PHOTO_RESULT);
    setClaimIndex(0);
    setStatus("photo");
  };

  const cancelPhoto = () => {
    setSelectedText("");
    setClaimMode("text");
    setVerification(TEXT_RESULT);
    setClaimIndex(0);
    setStatus("idle");
  };

  const openSettings = () => {
    setMenu(null);
    setFaqOpen(false);
    setSettingsReturnStatus((current) => (status === "settings" ? current : status));
    setStatus("settings");
  };

  const closeSettings = () => {
    setStatus(settingsReturnStatus || "idle");
  };

  const beginBubbleDrag = (event) => {
    if (event.button !== 0) return;

    const interactiveTarget = event.target.closest?.(
      "button, a, input, select, textarea"
    );
    if (interactiveTarget && interactiveTarget !== event.currentTarget) return;

    const dragRoot =
      event.currentTarget.closest(".iris-floating-wrap") || event.currentTarget;
    const rect = dragRoot.getBoundingClientRect();
    dragRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      startX: event.clientX,
      startY: event.clientY,
      width: rect.width,
      height: rect.height,
      moved: false,
    };

    event.currentTarget.setPointerCapture?.(event.pointerId);
    setBubbleDragging(true);
  };

  const moveBubble = (event) => {
    const drag = dragRef.current;
    if (!drag || event.pointerId !== drag.pointerId) return;

    const distance = Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY);
    if (distance > 4) drag.moved = true;

    setBubblePosition({
      x: clamp(event.clientX - drag.offsetX, 8, window.innerWidth - drag.width - 8),
      y: clamp(event.clientY - drag.offsetY, 8, window.innerHeight - drag.height - 8),
    });
  };

  const endBubbleDrag = (event) => {
    const drag = dragRef.current;
    if (!drag || event.pointerId !== drag.pointerId) return;

    event.currentTarget.releasePointerCapture?.(event.pointerId);
    suppressBubbleClickRef.current = drag.moved;
    dragRef.current = null;
    setBubbleDragging(false);

    window.setTimeout(() => {
      suppressBubbleClickRef.current = false;
    }, 0);
  };

  const expandBubble = () => {
    if (suppressBubbleClickRef.current) return;

    setBubblePosition((position) => {
      if (!position) return position;

      const panelWidth = Math.min(310, window.innerWidth - 24);
      const panelHeightEstimate = Math.min(560, window.innerHeight - 24);

      return {
        x: clamp(position.x, 8, window.innerWidth - panelWidth - 8),
        y: clamp(position.y, 8, window.innerHeight - panelHeightEstimate - 8),
      };
    });
    setCollapsed(false);
  };

  const floatingStyle = bubblePosition
    ? {
        left: `${bubblePosition.x}px`,
        top: `${bubblePosition.y}px`,
        right: "auto",
        bottom: "auto",
      }
    : undefined;

  return (
    <div className="mockup-app">
      <ChromeTopBar />
      <FacebookPage
        hasSelection={
          Boolean(selectedText) ||
          status === "scanning" ||
          status === "result" ||
          settingsReturnStatus === "result"
        }
        onContextMenu={handleContextMenu}
        onClaimSelect={selectClaim}
      />

      <div
        className={`iris-floating-wrap ${bubblePosition ? "is-positioned" : ""}`}
        style={floatingStyle}
      >
        <IrisWidget
          status={status}
          selectedText={selectedText || CLAIM}
          claimMode={claimMode}
          collapsed={collapsed}
          theme={theme}
          fontSize={fontSize}
          verification={verification}
          claimIndex={claimIndex}
          faqOpen={faqOpen}
          onCollapse={() => setCollapsed(true)}
          onExpand={expandBubble}
          onBubblePointerDown={beginBubbleDrag}
          onBubblePointerMove={moveBubble}
          onBubblePointerUp={endBubbleDrag}
          onCheck={beginCheck}
          onUploadPhoto={uploadPhoto}
          onCancelPhoto={cancelPhoto}
          onReset={reset}
          onPrevClaim={() => setClaimIndex((index) => Math.max(0, index - 1))}
          onNextClaim={() =>
            setClaimIndex((index) =>
              Math.min(verification.claims.length - 1, index + 1)
            )
          }
          onOpenSettings={openSettings}
          onCloseSettings={closeSettings}
          onOpenFaq={() => setFaqOpen(true)}
          onCloseFaq={() => setFaqOpen(false)}
          onThemeChange={setTheme}
          onFontSizeChange={setFontSize}
          bubbleDragging={bubbleDragging}
        />
      </div>

      <NativeContextMenu
        menu={menu}
        onCheck={beginCheck}
        onUploadPhoto={uploadPhoto}
        onClose={() => setMenu(null)}
      />
    </div>
  );
}
