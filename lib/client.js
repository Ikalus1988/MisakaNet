// ... existing code ...
  // Voice cues toggle (MisakaNetPanel)
  const renderVoiceToggle = () => {
    const voice = state.voiceCuesEnabled;
    return h("button", {
      className: "misakanet-voice-toggle",
      "aria-pressed": voice,
      role: "switch",
      onClick: () => {
        state.voiceCuesEnabled = !state.voiceCuesEnabled;
        applyVoiceCues(state.voiceCuesEnabled);
        render();
      },
    }, `Voice cues: ${voice ? "on" : "off"}`);
  };
// ... rest of file unchanged ...
