"""
voice_component.py — Browser SpeechRecognition → Streamlit bridge.

Architecture:
  1. Renders a microphone button via st.components.v1.html()
  2. Browser's webkitSpeechRecognition captures speech
  3. On final result, JS sets URL query param: ?voice_input=<encoded_text>
  4. Python polls st.query_params each render cycle
  5. When param found, it's returned and cleared

Works in: Chrome 33+, Edge 79+, Samsung Internet
Does NOT work in: Firefox (no SpeechRecognition support)
Fallback: mic button disabled, text input always available

No extra Python packages needed — pure browser JS + st.query_params.
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components
from typing import Optional


_VOICE_HTML = """
<!DOCTYPE html>
<html>
<head>
<style>
  body { margin: 0; padding: 0; background: transparent; font-family: sans-serif; }
  #voice-wrap {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
  }
  #mic-btn {
    padding: 7px 14px;
    border-radius: 8px;
    background: #0a1628;
    border: 1px solid #3b82f6;
    color: #93c5fd;
    font-weight: 700;
    cursor: pointer;
    font-size: 0.82rem;
    transition: all 0.2s;
  }
  #mic-btn:hover { background: #0d2035; }
  #mic-btn.listening {
    background: #1a0505;
    border-color: #ef4444;
    color: #fca5a5;
  }
  #mic-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  #voice-status {
    color: #64748b;
    font-size: 0.75rem;
    flex: 1;
  }
  #interim-text {
    color: #f97316;
    font-size: 0.78rem;
    font-style: italic;
    min-height: 18px;
    padding: 2px 4px;
  }
</style>
</head>
<body>
<div id="voice-wrap">
  <button id="mic-btn">🎤 Tap to Speak</button>
  <span id="voice-status"></span>
</div>
<div id="interim-text"></div>

<script>
(function() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const btn    = document.getElementById('mic-btn');
  const status = document.getElementById('voice-status');
  const interim = document.getElementById('interim-text');

  if (!SpeechRecognition) {
    btn.innerHTML = '⌨️ Type Only (voice not supported)';
    btn.disabled = true;
    status.textContent = 'Use text input below';
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous      = false;
  recognition.interimResults  = true;
  recognition.lang            = 'en-IN';
  recognition.maxAlternatives = 1;

  let isListening = false;

  function sendToStreamlit(text) {
    if (!text || !text.trim()) return;
    try {
      // Navigate parent window to include voice_input query param
      const url = new URL(window.parent.location.href);
      url.searchParams.set('voice_input', text.trim());
      window.parent.history.replaceState(null, '', url.toString());
      // Trigger Streamlit re-run by dispatching a hashchange-style event
      // The query_params polling in app.py will pick this up on next render
      window.parent.dispatchEvent(new Event('popstate'));
    } catch(e) {
      status.textContent = 'Error sending to app: ' + e.message;
    }
  }

  recognition.onstart = function() {
    isListening = true;
    btn.innerHTML = '🔴 Listening... (tap to stop)';
    btn.classList.add('listening');
    status.textContent = 'Speak now — capturing customer speech...';
    interim.textContent = '';
  };

  recognition.onresult = function(event) {
    let finalText   = '';
    let interimText = '';

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const t = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalText += t;
      } else {
        interimText += t;
      }
    }

    if (interimText) {
      interim.textContent = '"' + interimText + '"';
    }

    if (finalText.trim()) {
      sendToStreamlit(finalText.trim());
      status.textContent = 'Captured: "' + finalText.trim().slice(0,60) + '"';
      interim.textContent = '';
    }
  };

  recognition.onerror = function(event) {
    isListening = false;
    btn.innerHTML = '🎤 Tap to Speak';
    btn.classList.remove('listening');
    const msg = {
      'no-speech':     'No speech detected. Tap mic and try again.',
      'not-allowed':   'Microphone blocked. Allow microphone in browser.',
      'network':       'Network error. Check connection.',
      'aborted':       'Stopped.',
    }[event.error] || 'Error: ' + event.error;
    status.textContent = msg;
    interim.textContent = '';
  };

  recognition.onend = function() {
    isListening = false;
    btn.innerHTML = '🎤 Tap to Speak';
    btn.classList.remove('listening');
  };

  btn.addEventListener('click', function() {
    if (isListening) {
      recognition.stop();
    } else {
      try {
        recognition.start();
      } catch(e) {
        status.textContent = 'Could not start mic. Try again.';
      }
    }
  });

})();
</script>
</body>
</html>
"""


def render_voice_input(height: int = 85) -> None:
    """
    Render the microphone button in the current Streamlit column.
    Speech results are delivered via query params, polled by poll_voice_input().
    """
    components.html(_VOICE_HTML, height=height, scrolling=False)


def poll_voice_input() -> Optional[str]:
    """
    Check if a voice transcript arrived via URL query params.
    Must be called at the TOP of app.py render loop, before any state branches.

    Returns the captured text string and clears the param, or None.
    """
    try:
        params = st.query_params
        if "voice_input" in params:
            text = params["voice_input"]
            st.query_params.clear()
            if text and text.strip():
                return text.strip()
    except Exception:
        pass
    return None
