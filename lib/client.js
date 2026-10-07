// ... existing code ...
// Lines around 438-442: touchSession function
// Lines around 1502: MisakanetFooterAction

// I'll now make the necessary modifications

// Fix 1: Separate aria-label from live status region
// Fix 2: Surface session id in button title
// Fix 3: Add priority marker to guide card

const T = (key) => {
  // ... existing translations ...
}

// Around line 438: touchSession
function touchSession() {
  if (lastSessionId === undefined || lastSessionId === null) {
    return;
  }
  // Already exists, no change needed to logic
}

// Around line 1476: session id in clipboard output
// The clipboard already includes session id at line 1476, no change needed

// Fix 1 & 2: MisakanetFooterAction - update aria-label handling and title
function MisakanetFooterAction() {
  var note = currentSessionNote || "";
  var actionLabel = T("footer.action");
  var sessionId = lastSessionId || "unknown";
  
  // Build title with session id for clarity after session switches
  var titleText = T("footer.action") + " — " + T("footer.session_hint", sessionId);
  
  // Return structured component with separate aria-label and live region
  return {
    type: "button",
    "aria-label": actionLabel,  // Static, doesn't flip
    title: titleText,  // Shows session info
    children: [
      actionLabel,
      // Render note as separate live region instead of overwriting button name
      {
        type: "span",
        role: "status",
        "aria-live": "polite",
        children: note ? [note] : []
      }
    ]
  };
}

// Fix 3: Add priority type for extension cards in guide registry
// Update the type definition for guide cards to support priority field

var GuideCardPriority = {
  DEFAULT: "default",
  EXTENSION: "extension"
};

// Update registry to handle priority field
function registerGuideCard(card) {
  if (card.priority && card.priority !== GuideCardPriority.DEFAULT && 
      card.priority !== GuideCardPriority.EXTENSION) {
    throw new Error("Invalid guide card priority: " + card.priority);
  }
  // ... existing registration logic ...
  // Sort by priority: extension cards before default cards at same index
  var sortWeight = card.priority === GuideCardPriority.EXTENSION ? -1 : 0;
  cards.push({ ...card, _sortWeight: sortWeight });
  cards.sort((a, b) => a.index - b.index || a._sortWeight - b._sortWeight);
}

// Update MisakaNet guide card definition to include priority
var misakanetGuideCard = {
  type: "misakanet-panel",
  index: 3,
  priority: "extension",  // Mark as extension to prefer earlier positioning
  render: function() {
    // ... existing render logic ...
  }
};

// ... rest of existing code ...
