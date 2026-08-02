/* cordia tracker — first-party, ~2KB, no deps.
 * Sends a page-view ping, batches custom events, identifies session on the client.
 * No third-party. No fingerprinting. Sets one cookie: cordia_anon (1y, sameSite=lax). */
(function(){
  if (window.__cordiaT) return; window.__cordiaT=1;
  var T='/t.js'.replace('t.js','t');  // base = /t
  var Q=function(o){return Object.keys(o).filter(function(k){return o[k]!=null&&o[k]!=='';})
    .map(function(k){return encodeURIComponent(k)+'='+encodeURIComponent(o[k]);}).join('&');};
  function uuidv4(){
    var b=crypto.getRandomValues(new Uint8Array(16));
    b[6]=(b[6]&0x0f)|0x40; b[8]=(b[8]&0x3f)|0x80;
    return Array.from(b,function(x){return x.toString(16).padStart(2,'0');}).join('')
      .replace(/(.{8})(.{4})(.{4})(.{4})(.{12})/,'$1-$2-$3-$4-$5');
  }
  function setCookie(n,v,d){
    var t=new Date(); t.setTime(t.getTime()+d*864e5);
    document.cookie=n+'='+v+'; expires='+t.toUTCString()+'; path=/; SameSite=Lax';
  }
  function getCookie(n){
    return document.cookie.split('; ').reduce(function(a,c){
      var p=c.split('='); return p[0]===n?decodeURIComponent(p[1]):a;
    },'');
  }
  var anon=getCookie('cordia_anon');
  if(!anon){ anon=uuidv4(); setCookie('cordia_anon', anon, 365); }
  var SESSION_KEY='cordia_session';
  var sess=sessionStorage.getItem(SESSION_KEY);
  if(!sess){ sess=uuidv4(); sessionStorage.setItem(SESSION_KEY, sess); }

  function ping(){
    var sw=screen.width||0, sh=screen.height||0;
    var img=new Image();
    img.src=T+'/p?'+Q({u:anon,s:sess,p:location.pathname+location.search,
      r:document.referrer||'',lang:(navigator.language||'').slice(0,12),
      sw:sw,sh:sh});
  }

  var q=[]; function flush(){
    while(q.length){
      var e=q.shift();
      var img=new Image();
      img.src=T+'/e?'+Q({u:anon,s:sess,k:e.k,m:JSON.stringify(e.m||{}),p:location.pathname});
    }
  }
  window.cordiaTrack=function(k,m){ q.push({k:k,m:m||{}}); if(q.length>=8) flush(); };
  window.addEventListener('beforeunload', flush);
  setInterval(flush, 12000);

  if(document.readyState==='complete') ping();
  else window.addEventListener('load', ping);
})();
