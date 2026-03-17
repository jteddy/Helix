/**
 * index.html — PATCH for Bug 6 (WebSocket ping interval leak)
 * =============================================================
 *
 * Every call to wsConnect() (which fires on every disconnect/reconnect)
 * was registering a NEW setInterval for the 10-second ping without ever
 * clearing the previous one.  After repeated reconnects the pings stack
 * up and flood the server's receive_text() handler.
 *
 * FIND this block near the top of the <script> section:
 * ------------------------------------------------------
 *
 *   let ws;
 *   function wsConnect(){
 *     const proto=location.protocol==='https:'?'wss:':'ws:';
 *     ws=new WebSocket(`${proto}//${location.host}/ws`);
 *     ws.onopen=()=>{$('s-ws').textContent='Connected';$('s-ws').style.color='var(--green)';setInterval(()=>{if(ws.readyState===1)ws.send('ping');},10000);};
 *     ws.onmessage=e=>applyStatus(JSON.parse(e.data));
 *     ws.onclose=()=>{$('ws-dot').className='err';$('s-ws').textContent='Reconnecting…';$('s-ws').style.color='var(--red)';setTimeout(wsConnect,2000);};
 *   }
 *   wsConnect();
 *
 *
 * REPLACE WITH:
 * -------------
 *
 *   let ws;
 *   let _wsPingInterval;   // FIX 6: track the interval so we can clear it on reconnect
 *   function wsConnect(){
 *     const proto=location.protocol==='https:'?'wss:':'ws:';
 *     ws=new WebSocket(`${proto}//${location.host}/ws`);
 *     ws.onopen=()=>{
 *       $('s-ws').textContent='Connected';
 *       $('s-ws').style.color='var(--green)';
 *       clearInterval(_wsPingInterval);   // FIX 6: kill the old interval before making a new one
 *       _wsPingInterval=setInterval(()=>{if(ws.readyState===1)ws.send('ping');},10000);
 *     };
 *     ws.onmessage=e=>applyStatus(JSON.parse(e.data));
 *     ws.onclose=()=>{$('ws-dot').className='err';$('s-ws').textContent='Reconnecting…';$('s-ws').style.color='var(--red)';setTimeout(wsConnect,2000);};
 *   }
 *   wsConnect();
 *
 *
 * Minified form (drop-in for the compact single-line style used in the file):
 * ---------------------------------------------------------------------------
 *
 *   let ws;let _wsPingInterval;
 *   function wsConnect(){
 *     const proto=location.protocol==='https:'?'wss:':'ws:';
 *     ws=new WebSocket(`${proto}//${location.host}/ws`);
 *     ws.onopen=()=>{$('s-ws').textContent='Connected';$('s-ws').style.color='var(--green)';clearInterval(_wsPingInterval);_wsPingInterval=setInterval(()=>{if(ws.readyState===1)ws.send('ping');},10000);};
 *     ws.onmessage=e=>applyStatus(JSON.parse(e.data));
 *     ws.onclose=()=>{$('ws-dot').className='err';$('s-ws').textContent='Reconnecting…';$('s-ws').style.color='var(--red)';setTimeout(wsConnect,2000);};
 *   }
 *   wsConnect();
 */
