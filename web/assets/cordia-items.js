/* Cordia item engine — Archetypes A (cold intent), C (live task v1→v2),
   D (escalation hybrid), E (critique). Client-side only. Responses persist
   to localStorage under cordia-responses. No scoring — corpus capture only.
   Scoring pipeline (rubric → κ → judge) is server-side, not built yet. */

const CordiaItems = (() => {
  const KEY = 'cordia-responses';
  const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1' ? 'http://127.0.0.1:9995' : location.protocol + '//' + location.hostname + (location.protocol === 'https:' ? '' : ':9995'));
  const learner = () => localStorage.getItem('cordia-learner') || 'anon';
  const load = () => JSON.parse(localStorage.getItem(KEY) || '{}');
  const save = (trackId, block, value) => {
    const all = load();
    all[trackId] = all[trackId] || {};
    all[trackId][block] = { value, ts: new Date().toISOString() };
    localStorage.setItem(KEY, JSON.stringify(all));
    // fire-and-forget ingest to corpus server (session token attaches the real account)
    try {
      fetch(API + '/train/respond', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({track: trackId, block, value, learner: learner(),
                              token: localStorage.getItem('cordia-token') || ''})
      }).catch(()=>{});
    } catch(e) {}
  };
  const get = (trackId, block) => (load()[trackId] || {})[block]?.value || null;
  const progress = (trackId) => {
    const t = load()[trackId] || {};
    const blocks = ['A','C1','C2','D','Dwhy','E'];
    return blocks.filter(b => t[b]).length; // out of 6
  };

  function el(html){ const d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstChild; }

  function textBlock(trackId, block, label, placeholder, hint){
    const prev = get(trackId, block);
    const wrap = el(`<div class="item-block">
      <div class="ib-label"><span class="ib-tag">${block}</span>${label}</div>
      ${hint ? `<p class="ib-hint">${hint}</p>` : ''}
      <textarea class="ib-input" rows="5" placeholder="${placeholder}">${prev || ''}</textarea>
      <div class="ib-foot">
        <button class="ib-mic" title="Speak instead of typing" style="display:none">🎙</button>
        <span class="ib-saved">${prev ? 'saved' : ''}</span>
      <button class="btn btn-primary ib-save">Save</button></div>
    </div>`);
    const ta = wrap.querySelector('.ib-input');
    const saved = wrap.querySelector('.ib-saved');
    const doSave = () => { save(trackId, block, ta.value); saved.textContent = 'saved ✓'; };
    wrap.querySelector('.ib-save').onclick = doSave;
    let t; ta.oninput = () => { saved.textContent=''; clearTimeout(t); t=setTimeout(()=>{ if(ta.value.trim()) doSave(); }, 1500); };

    /* Speech capture — tracks 6/7/15 measure typing if you force typing.
       Web Speech API, browser-native, no install. Chrome/Edge only. */
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if(SR){
      const mic = wrap.querySelector('.ib-mic');
      mic.style.display = '';
      let rec = null, listening = false;
      mic.onclick = e => {
        e.preventDefault();
        if(listening){ rec.stop(); return; }
        rec = new SR();
        rec.lang = 'en-US'; rec.continuous = true; rec.interimResults = true;
        rec.onresult = ev => {
          let final = '';
          for(let i = ev.resultIndex; i < ev.results.length; i++){
            if(ev.results[i].isFinal) final += ev.results[i][0].transcript + ' ';
          }
          if(final){ ta.value = (ta.value + ' ' + final).trim(); ta.dispatchEvent(new Event('input')); }
        };
        rec.onend = () => { listening = false; mic.classList.remove('recording'); };
        rec.onerror = () => { listening = false; mic.classList.remove('recording'); };
        rec.start();
        listening = true; mic.classList.add('recording');
      };
    }
    return wrap;
  }

  function escalationBlock(trackId){
    const prev = get(trackId, 'D');
    const opts = [
      ['proceed','Proceed — accept the output as-is'],
      ['verify','Proceed with verification — check the parts that carry risk'],
      ['escalate','Escalate — stop and involve a human with authority']
    ];
    const wrap = el(`<div class="item-block">
      <div class="ib-label"><span class="ib-tag">D</span>Escalation judgment</div>
      <p class="ib-hint">Whether you escalate is scoreable. Why is the corpus. Answer both.</p>
      <div class="ib-opts"></div>
      <textarea class="ib-input" rows="4" placeholder="Why is that the right call here?">${get(trackId,'Dwhy')||''}</textarea>
      <div class="ib-foot"><span class="ib-saved"></span><button class="btn btn-primary ib-save">Save</button></div>
    </div>`);
    const optBox = wrap.querySelector('.ib-opts');
    opts.forEach(([v,txt]) => {
      const o = el(`<label class="ib-opt"><input type="radio" name="esc" value="${v}" ${prev===v?'checked':''}><span>${txt}</span></label>`);
      optBox.appendChild(o);
    });
    const saved = wrap.querySelector('.ib-saved');
    const ta = wrap.querySelector('.ib-input');
    wrap.querySelector('.ib-save').onclick = () => {
      const sel = wrap.querySelector('input[name=esc]:checked');
      if(sel) save(trackId,'D',sel.value);
      save(trackId,'Dwhy',ta.value);
      saved.textContent='saved ✓';
    };
    return wrap;
  }

  function critiqueBlock(trackId, critiqueText, revealAnswer){
    const wrap = el(`<div class="item-block">
      <div class="ib-label"><span class="ib-tag">E</span>Critique the output</div>
      ${critiqueText ? `<div class="ib-artifact"><div class="ib-artifact-label">AI output under review</div>${critiqueText}</div>` : ''}
    </div>`);
    wrap.appendChild(textBlock(trackId,'E',"Your critique","What's wrong with this output? Be specific — name the defect, not just the feeling.",
      "Sensitivity to seeded defects is tracked over time as your automation-bias resistance (d′)."));
    if(revealAnswer){
      const btn = el(`<button class="btn btn-outline ib-reveal">Compare with the seeded defect</button>`);
      const ans = el(`<div class="ib-answer" style="display:none"><div class="ib-artifact-label">Seeded defect — the answer key</div>${revealAnswer}</div>`);
      btn.onclick = () => { ans.style.display = ans.style.display==='none' ? 'block':'none'; btn.textContent = ans.style.display==='none' ? 'Compare with the seeded defect' : 'Hide the answer key'; };
      wrap.appendChild(btn); wrap.appendChild(ans);
    }
    return wrap;
  }

  /* Live LLM panel — the real Archetype C. Sends the learner's instruction to the
     backend proxy; the agent's reply is displayed and can be used as artifact v1 context. */
  function liveAgentPanel(trackId, envKey){
    const wrap = el(`<div class="item-block live-panel">
      <div class="ib-label"><span class="ib-tag">C</span>Live environment — instruct the agent</div>
      <p class="ib-hint">This is a real agent. Give it your instruction for the scenario above. Its output is yours to critique and revise — that exchange is the corpus.</p>
      <textarea class="ib-input" rows="3" placeholder="Your instruction to the agent…"></textarea>
      <div class="ib-foot"><span class="ib-status"></span>
        <button class="btn btn-gold ib-send">Send to agent</button></div>
      <div class="ib-reply" style="display:none">
        <div class="ib-artifact-label">Agent output</div>
        <div class="ib-reply-text"></div>
        <button class="btn btn-outline ib-tocritique" style="margin-top:12px;padding:8px 18px;font-size:12.5px">Use this output below (v1 context)</button>
      </div>
    </div>`);
    const ta = wrap.querySelector('.ib-input');
    const status = wrap.querySelector('.ib-status');
    const reply = wrap.querySelector('.ib-reply');
    const replyText = wrap.querySelector('.ib-reply-text');
    const sendBtn = wrap.querySelector('.ib-send');
    sendBtn.onclick = async () => {
      const instruction = ta.value.trim();
      if(!instruction) return;
      sendBtn.disabled = true; status.textContent = 'agent is working…';
      save(trackId, 'C-instruction', instruction);
      try {
        const r = await fetch(API + '/train/llm', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({env: envKey, instruction,
                                token: localStorage.getItem('cordia-token') || ''})
        });
        const d = await r.json();
        if(d.ok){
          replyText.textContent = d.output;
          reply.style.display = 'block';
          save(trackId, 'C-agent-output', d.output);
          status.textContent = 'received ✓';
        } else { status.textContent = (d.error || 'unknown'); if(r.status===401) status.textContent = 'sign in to use the live environment'; }
      } catch(e){ status.textContent = 'agent unreachable — is the backend running?'; }
      sendBtn.disabled = false;
    };
    wrap.querySelector('.ib-tocritique').onclick = () => {
      const c1 = document.querySelectorAll('.ib-input');
      // drop the agent output into the v1 artifact field (first C1 textarea after this panel)
      for(const t of c1){ if(t !== ta && !t.value){ t.value = replyText.textContent; break; } }
    };
    return wrap;
  }

  return { textBlock, escalationBlock, critiqueBlock, liveAgentPanel, progress, save, get };
})();
