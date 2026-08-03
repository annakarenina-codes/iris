import React, { useEffect, useId, useRef, useState } from "react";

const CLAIM =
  "Number 1 parin si Duterte sa Survey! Kahit anong paninira nila, panalo parin tayo!";

const OCR_CLAIM =
  "Viral post claims a candidate has already been declared the winner of the 2028 presidential survey.";

const SOURCES = [
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
];

function IrisEye({ size = 26, monochrome = false }) {
  const gradientId = useId();
  const fill = monochrome ? "currentColor" : `url(#${gradientId})`;

  return (
    <svg width={size} height={size} viewBox="0 0 100 100" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="100" x2="100" y2="0" gradientUnits="userSpaceOnUse">
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
      <circle cx="44" cy="43" r="4" fill="white" opacity="0.72" />
      <line x1="64" y1="62" x2="78" y2="76" stroke={fill} strokeWidth="8" strokeLinecap="round" />
    </svg>
  );
}

function Icon({ name, size = 18 }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };

  const paths = {
    hand: <path d="M7 11V7.5a1.5 1.5 0 0 1 3 0V11m0-3.5a1.5 1.5 0 0 1 3 0V11m0-2.5a1.5 1.5 0 0 1 3 0V13m0-2.5a1.5 1.5 0 0 1 3 0V14a7 7 0 0 1-14 0v-2.5a1.5 1.5 0 0 1 3 0V14" />,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
    news: <><path d="M4 5h13a3 3 0 0 1 3 3v11H7a3 3 0 0 1-3-3V5Z" /><path d="M8 9h7M8 13h8M8 17h5" /></>,
    image: <><rect x="4" y="5" width="16" height="14" rx="2" /><path d="m4 15 4-4 4 4 2-2 6 6" /><circle cx="15.5" cy="9.5" r="1.5" /></>,
    power: <><path d="M12 3v8" /><path d="M7.05 7.05a7 7 0 1 0 9.9 0" /></>,
    search: <path d="M10.8 18a7.2 7.2 0 1 1 5.1-2.1L20 20" />,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
    message: <path d="M5 18.5V6a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9l-4 2.5Z" />,
    close: <path d="m7 7 10 10M17 7 7 17" />,
    external: <><path d="M7 7h10v10" /><path d="M17 7 7 17" /><path d="M15 17H7V9" /></>,
  };

  return <svg {...common}>{paths[name]}</svg>;
}

function StatusBar({ light = false }) {
  return (
    <div className={`status-bar ${light ? "is-light" : ""}`}>
      <span>9:41</span>
      <div>
        <span className="signal-bars" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span>5G</span>
        <span className="battery" aria-hidden="true" />
      </div>
    </div>
  );
}

function Toggle({ enabled, onToggle }) {
  return (
    <button className={`iris-toggle ${enabled ? "is-on" : ""}`} type="button" onClick={onToggle} aria-pressed={enabled}>
      <span>
        <IrisEye size={enabled ? 16 : 15} />
      </span>
    </button>
  );
}

function HomeScreen({ enabled, onToggle }) {
  const cards = [
    {
      icon: "hand",
      title: "User-triggered only",
      desc: "IRIS only activates when you select text. It never reads your screen automatically.",
    },
    {
      icon: "lock",
      title: "Privacy first",
      desc: "No browsing history stored. Each check is forgotten immediately after results are shown.",
    },
    {
      icon: "news",
      title: "6 PH news sources",
      desc: "GMA, Inquirer, PhilStar, MB, PNA, PIA, plus VERA Files for verified fact-checks.",
    },
  ];

  return (
    <section className="screen home-screen">
      <header className="home-hero">
        <StatusBar light />
        <div className="home-hero__brand">
          <IrisEye size={36} />
          <div>
            <h1>IRIS</h1>
            <p>INTELLIGENT REAL-TIME INFORMATION SCANNER</p>
          </div>
        </div>
      </header>

      <main className="home-content">
        <section className="bubble-card">
          <div className={`bubble-preview ${enabled ? "is-on" : ""}`}>
            <IrisEye size={34} monochrome={enabled} />
          </div>
          <h2>IRIS Bubble</h2>
          <p>
            {enabled
              ? "IRIS is active. Select text in any app and tap Check with IRIS to fact-check."
              : "IRIS is disabled. Enable it to show the floating bubble over other apps."}
          </p>
          <Toggle enabled={enabled} onToggle={onToggle} />
          <strong className={enabled ? "is-enabled" : ""}>
            {enabled ? "ON - Bubble is visible" : "OFF - Bubble is hidden"}
          </strong>
        </section>

        <div className="info-stack">
          {cards.map((card) => (
            <article className="info-card" key={card.title}>
              <span>
                <Icon name={card.icon} size={17} />
              </span>
              <div>
                <h3>{card.title}</h3>
                <p>{card.desc}</p>
              </div>
            </article>
          ))}
        </div>
      </main>
    </section>
  );
}

function FacebookApp({
  phase,
  claimText,
  claimMode,
  menuOpen,
  onSelect,
  onCheck,
  onDismiss,
  onBubbleClick,
  onUploadPhoto,
  onTurnOff,
  onCancelPhoto,
}) {
  const selected = phase === "selected" || phase === "scanning" || phase === "result";

  return (
    <section className="screen facebook-screen">
      <header className="facebook-appbar">
        <StatusBar />
        <div className="facebook-row">
          <div className="fb-mobile-logo">f</div>
          <div className="facebook-actions">
            <button type="button" aria-label="Search">
              <Icon name="search" size={16} />
            </button>
            <button type="button" aria-label="Messenger">
              <Icon name="message" size={16} />
            </button>
            <button type="button" aria-label="Notifications">
              <Icon name="bell" size={16} />
            </button>
          </div>
        </div>
      </header>

      <main className="mobile-feed">
        <article className="mobile-post">
          <header>
            <div className="avatar-red">KB</div>
            <div>
              <strong>Congressman Kiko Barzaga</strong>
              <span>7h · Public</span>
            </div>
          </header>

          <p className="mobile-post__caption">
            Sharing this because people deserve to know the truth.
          </p>

          <div className={`mobile-claim ${selected ? "is-selected" : ""}`} onClick={onSelect} onDoubleClick={onSelect}>
            <div className="mobile-claim__photo" />
            <div className="mobile-claim__text">
              <p>{CLAIM}</p>
              <span>#Duterte2028</span>
            </div>
          </div>

          <div className="mobile-post__metrics">
            <span>14K reactions</span>
            <span>3.1K shares</span>
          </div>
          <div className="mobile-post__actions">
            <button type="button">Like</button>
            <button type="button">Comment</button>
            <button type="button">Share</button>
          </div>
        </article>

        <article className="feed-placeholder" aria-hidden="true">
          <span />
          <span />
          <div />
        </article>
      </main>

      {phase === "selected" && <SelectionToolbar onCheck={onCheck} />}
      {phase === "scanning" && <ScanningCard claimText={claimText} />}
      <FloatingBubble
        phase={phase}
        claimText={claimText}
        claimMode={claimMode}
        menuOpen={menuOpen}
        onBubbleClick={onBubbleClick}
        onDismiss={onDismiss}
        onUploadPhoto={onUploadPhoto}
        onTurnOff={onTurnOff}
        onCheckPhoto={() => onCheck("photo")}
        onCancelPhoto={onCancelPhoto}
      />
    </section>
  );
}

function SelectionToolbar({ onCheck }) {
  return (
    <div className="selection-toolbar">
      <button type="button">Copy</button>
      <button type="button">All</button>
      <button type="button">Share</button>
      <button className="toolbar-iris" type="button" onClick={() => onCheck()}>
        <IrisEye size={12} monochrome />
        Check with IRIS
      </button>
    </div>
  );
}

function ScanningCard({ claimText }) {
  const rows = [
    ["VERA Files", "done"],
    ["GMA Network", "done"],
    ["Inquirer", "done"],
    ["PhilStar", "active"],
    ["Manila Bulletin", "waiting"],
    ["PNA + PIA", "waiting"],
  ];

  return (
    <div className="scan-card">
      <div className="scan-card__head">
        <span className="scan-orb">
          <IrisEye size={21} monochrome />
        </span>
        <div>
          <strong>Scanning sources...</strong>
          <p>Checking claim against Philippine outlets</p>
        </div>
      </div>

      <blockquote>{claimText}</blockquote>

      <div className="source-progress">
        {rows.map(([name, state]) => (
          <div className={`source-progress__row is-${state}`} key={name}>
            <span />
            <strong>{name}</strong>
            <em>{state === "done" ? "Searched" : state === "active" ? "Scanning" : "Waiting"}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

function FloatingBubble({
  phase,
  claimText,
  claimMode,
  menuOpen,
  onBubbleClick,
  onDismiss,
  onUploadPhoto,
  onTurnOff,
  onCheckPhoto,
  onCancelPhoto,
}) {
  const active = phase === "scanning" || phase === "result";

  return (
    <div className="bubble-layer">
      <button className={`floating-bubble ${active ? "is-active" : ""}`} type="button" onClick={onBubbleClick}>
        <IrisEye size={active ? 28 : 24} monochrome={active} />
      </button>
      {phase === "idle" && menuOpen && (
        <IdleBubbleMenu onUploadPhoto={onUploadPhoto} onTurnOff={onTurnOff} />
      )}
      {phase === "photo" && (
        <PhotoUploadPanel onScan={onCheckPhoto} onCancel={onCancelPhoto} />
      )}
      {phase === "result" && (
        <ResultPanel
          claimText={claimText}
          claimMode={claimMode}
          onDismiss={onDismiss}
        />
      )}
    </div>
  );
}

function IdleBubbleMenu({ onUploadPhoto, onTurnOff }) {
  return (
    <aside className="idle-menu">
      <header>
        <IrisEye size={18} />
        <div>
          <strong>IRIS</strong>
          <span>READY</span>
        </div>
      </header>
      <main>
        <div className="idle-empty">
          <span>No selected text</span>
          <button type="button" disabled>
            Check with IRIS
          </button>
        </div>
        <button className="menu-action is-primary" type="button" onClick={onUploadPhoto}>
          <Icon name="image" size={16} />
          Upload photo
        </button>
        <button className="menu-action" type="button" onClick={onTurnOff}>
          <Icon name="power" size={16} />
          Turn off bubble
        </button>
      </main>
    </aside>
  );
}

function PhotoUploadPanel({ onScan, onCancel }) {
  return (
    <aside className="photo-panel">
      <header>
        <IrisEye size={18} />
        <div>
          <strong>IRIS</strong>
          <span>IMAGE OCR</span>
        </div>
        <button type="button" aria-label="Close upload panel" onClick={onCancel}>
          <Icon name="close" size={14} />
        </button>
      </header>
      <main>
        <div className="photo-preview">
          <span>campaign-card.jpg</span>
          <p>{OCR_CLAIM}</p>
        </div>
        <div className="ocr-preview">
          <span>Detected text preview</span>
          <blockquote>{OCR_CLAIM}</blockquote>
        </div>
        <button className="scan-photo-button" type="button" onClick={onScan}>
          Scan image text
        </button>
      </main>
    </aside>
  );
}

function ResultPanel({ claimText, claimMode, onDismiss }) {
  return (
    <aside className="result-panel">
      <header>
        <IrisEye size={18} />
        <strong>IRIS</strong>
        <span>RESULT</span>
        <button type="button" aria-label="Dismiss result" onClick={onDismiss}>
          <Icon name="close" size={14} />
        </button>
      </header>

      <main>
        <div className="result-claim">
          {claimMode === "photo" && <span>Text extracted from image</span>}
          <blockquote>{claimText}</blockquote>
        </div>

        <div className="political-compact">
          <span aria-hidden="true">!</span>
          <div>
            <strong>Politically Sensitive</strong>
            <p>Apply extra scrutiny before sharing.</p>
          </div>
        </div>

        <div className="verdict-mobile">
          <span>⚠️</span>
          <div>
            <strong>Partially Verified</strong>
            <p>Survey data found, but the ranking is not directly confirmed.</p>
          </div>
        </div>

        <div className="corroboration-mobile">
          <strong>2 of 6</strong>
          <span>sources matched</span>
        </div>

        <div className="mobile-related">Related Articles</div>
        <div className="mobile-sources">
          {SOURCES.map((source) => (
            <button type="button" key={source.outlet}>
              <span>
                <strong>{source.outlet}</strong>
                <time>{source.date}</time>
              </span>
              <em>{source.title}</em>
              <small>
                <Icon name="external" size={10} />
                Read article
              </small>
            </button>
          ))}
        </div>

        <p className="mobile-disclaimer">
          IRIS is an assistant, not an authority. Read sources before sharing.
        </p>
      </main>
    </aside>
  );
}

function PhoneFrame({ children }) {
  return (
    <div className="phone-frame" aria-label="Android phone mockup">
      <div className="phone-speaker" />
      <div className="phone-screen">{children}</div>
      <div className="home-indicator" />
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState("home");
  const [enabled, setEnabled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [claimText, setClaimText] = useState(CLAIM);
  const [claimMode, setClaimMode] = useState("text");
  const timerRef = useRef(null);

  useEffect(() => () => clearTimeout(timerRef.current), []);

  const enableBubble = () => {
    setEnabled((current) => {
      const next = !current;
      clearTimeout(timerRef.current);
      if (next) {
        timerRef.current = setTimeout(() => setScreen("idle"), 450);
      } else {
        setScreen("home");
      }
      setMenuOpen(false);
      return next;
    });
  };

  const selectText = () => {
    if (enabled && screen === "idle") {
      setClaimText(CLAIM);
      setClaimMode("text");
      setMenuOpen(false);
      setScreen("selected");
    }
  };

  const checkClaim = (mode = claimMode) => {
    if (mode === "photo") {
      setClaimText(OCR_CLAIM);
      setClaimMode("photo");
    }
    setScreen("scanning");
    setMenuOpen(false);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setScreen("result"), 2800);
  };

  const dismissResult = () => {
    if (screen === "result") setScreen("idle");
    setMenuOpen(false);
  };

  const handleBubbleClick = () => {
    if (screen === "idle") {
      setMenuOpen((current) => !current);
      return;
    }
    if (screen === "photo") {
      setScreen("idle");
      return;
    }
    if (screen === "result") {
      dismissResult();
    }
  };

  const openPhotoUpload = () => {
    setClaimText(OCR_CLAIM);
    setClaimMode("photo");
    setMenuOpen(false);
    setScreen("photo");
  };

  const turnOffBubble = () => {
    clearTimeout(timerRef.current);
    setEnabled(false);
    setMenuOpen(false);
    setScreen("home");
  };

  const cancelPhotoUpload = () => {
    setMenuOpen(false);
    setScreen("idle");
  };

  return (
    <div className="app-shell">
      <PhoneFrame>
        {screen === "home" ? (
          <HomeScreen enabled={enabled} onToggle={enableBubble} />
        ) : (
          <FacebookApp
            phase={screen}
            claimText={claimText}
            claimMode={claimMode}
            menuOpen={menuOpen}
            onSelect={selectText}
            onCheck={checkClaim}
            onDismiss={dismissResult}
            onBubbleClick={handleBubbleClick}
            onUploadPhoto={openPhotoUpload}
            onTurnOff={turnOffBubble}
            onCancelPhoto={cancelPhotoUpload}
          />
        )}
      </PhoneFrame>
    </div>
  );
}
