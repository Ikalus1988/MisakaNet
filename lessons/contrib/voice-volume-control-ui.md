/**
 * VoiceVolumeControl
 * Wires up the volume slider and mute button to a target HTMLMediaElement
 * (or any object with a .volume property between 0 and 1).
 *
 * Usage:
 *   const ctrl = new VoiceVolumeControl(document.querySelector('.volume-control'), audioEl);
 *   ctrl.setVolume(0.5);   // programmatic control
 *   ctrl.destroy();        // cleanup listeners
 */
class VoiceVolumeControl {
  /**
   * @param {HTMLElement} container  - The .volume-control wrapper element
   * @param {HTMLMediaElement|null} mediaEl - Optional audio/video element to control
   */
  constructor(container, mediaEl = null) {
    this._container = container;
    this._mediaEl = mediaEl;
    this._slider = container.querySelector('#voice-volume-slider');
    this._output = container.querySelector('.volume-value');
    this._muteBtn = container.querySelector('#voice-mute-btn');
    this._prevVolume = parseInt(this._slider?.value ?? 80, 10);
    this._muted = false;

    if (!this._slider) {
      console.warn('[VoiceVolumeControl] slider not found');
      return;
    }

    this._onSliderInput = this._handleSliderInput.bind(this);
    this._onMuteClick = this._handleMuteClick.bind(this);
    this._onKeydown = this._handleKeydown.bind(this);

    this._slider.addEventListener('input', this._onSliderInput);
    if (this._muteBtn) {
      this._muteBtn.addEventListener('click', this._onMuteClick);
    }
    this._slider.addEventListener('keydown', this._onKeydown);

    // Sync initial state
    this._applyVolume(parseInt(this._slider.value, 10));
  }

  /** @param {number} pct - 0..100 */
  setVolume(pct) {
    const clamped = Math.max(0, Math.min(100, Math.round(pct)));
    if (this._slider) {
      this._slider.value = String(clamped);
    }
    this._muted = false;
    this._applyVolume(clamped);
  }

  get volume() {
    return parseInt(this._slider?.value ?? 80, 10);
  }

  get muted() {
    return this._muted;
  }

  destroy() {
    if (this._slider) {
      this._slider.removeEventListener('input', this._onSliderInput);
      this._slider.removeEventListener('keydown', this._onKeydown);
    }
    if (this._muteBtn) {
      this._muteBtn.removeEventListener('click', this._onMuteClick);
    }
  }

  // ── private ──

  _handleSliderInput(e) {
    const pct = parseInt(e.target.value, 10);
    if (this._muted && pct > 0) {
      this._muted = false;
      this._updateMuteBtn();
    }
    this._prevVolume = pct || this._prevVolume;
    this._applyVolume(pct);
  }

  _handleMuteClick() {
    this._muted = !this._muted;
    if (this._muted) {
      this._prevVolume = parseInt(this._slider.value, 10) || 80;
      this._slider.value = '0';
      this._applyVolume(0);
    } else {
      this._slider.value = String(this._prevVolume);
      this._applyVolume(this._prevVolume);
    }
    this._updateMuteBtn();
  }

  /** Allow arrow keys to move in steps of 5 */
  _handleKeydown(e) {
    let delta = 0;
    if (e.key === 'ArrowUp' || e.key === 'ArrowRight') delta = 5;
    else if (e.key === 'ArrowDown' || e.key === 'ArrowLeft') delta = -5;
    if (delta === 0) return;
    e.preventDefault();
    const newVal = Math.max(0, Math.min(100, parseInt(this._slider.value, 10) + delta));
    this._slider.value = String(newVal);
    this._slider.dispatchEvent(new Event('input'));
  }

  _applyVolume(pct) {
    // Update ARIA
    if (this._slider) {
      this._slider.setAttribute('aria-valuenow', String(pct));
    }
    // Update text output
    if (this._output) {
      this._output.textContent = `${pct}%`;
    }
    // Update CSS gradient fill
    if (this._slider) {
      this._slider.style.setProperty('--pct', `${pct}%`);
    }
    // Update icon
    if (this._container) {
      const icon = this._container.querySelector('.volume-icon');
      if (icon) {
        icon.textContent = pct === 0 ? '🔇' : pct < 40 ? '🔉' : '🔊';
      }
    }
    // Drive the actual media element
    if (this._mediaEl) {
      this._mediaEl.volume = pct / 100;
      this._mediaEl.muted = pct === 0;
    }
    // Fire custom event so other parts of the page can react
    this._container?.dispatchEvent(new CustomEvent('volumechange', {
      bubbles: true,
      detail: { volume: pct / 100, pct, muted: pct === 0 },
    }));
  }

  _updateMuteBtn() {
    if (!this._muteBtn) return;
    this._muteBtn.setAttribute('aria-pressed', String(this._muted));
    this._muteBtn.setAttribute('aria-label', this._muted ? 'Unmute voice' : 'Mute voice');
  }
}

// ── Auto-init on DOMContentLoaded ──
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.volume-control').forEach((container) => {
    const targetId = container.dataset.mediaTarget;
    const mediaEl = targetId ? document.getElementById(targetId) : null;
    container._volumeControl = new VoiceVolumeControl(container, mediaEl);
  });
});