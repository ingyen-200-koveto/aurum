const $=id=>document.getElementById(id);
const fmt=n=>n===null||n===undefined?'–':Number(n).toLocaleString('hu-HU',{maximumFractionDigits:5});
const dateFmt=v=>{if(!v)return '–';const d=new Date(v);return isNaN(d)?String(v):d.toLocaleString('hu-HU')};
const clsResult=r=>['TAKE_PROFIT_3','TP1_LOCKED'].includes(r)?'win':r==='STOP_LOSS'?'loss':'';

function render(data){
 const online=data.bot.online;
 $('botDot').className='dot '+(online?'online':'offline');
 $('botStatus').textContent=online?'BOT ONLINE':'BOT OFFLINE';
 $('lastUpdate').textContent='Frissítve: '+new Date().toLocaleTimeString('hu-HU');
 $('systemBot').textContent=online?'ONLINE':'OFFLINE';
 $('systemMt5').textContent=data.bot.mt5_status;
 $('mt5Status').textContent=data.bot.mt5_status;
 $('mt5Status').className='pill '+(online?'good':'neutral');
 $('dailyCount').textContent=data.state.daily_signal_count??0;
 $('cooldown').textContent=dateFmt(data.state.cooldown_until);
 $('dataAge').textContent=data.bot.state_file_age_seconds===null?'Nincs adat':`${data.bot.state_file_age_seconds} mp`;

 const s=data.state.active_signal;
 $('noSignal').classList.toggle('hidden',!!s);
 $('signalContent').classList.toggle('hidden',!s);
 if(s){
  $('signalStatus').textContent=s.status||'ACTIVE';$('signalStatus').className='pill good';
  $('signalSymbol').textContent=s.symbol||'–';$('signalDirection').textContent=s.direction||'–';
  $('signalDirection').className=(s.direction||'').toUpperCase()==='SELL'?'sell':'';
  $('entry').textContent=fmt(s.entry_price);$('sl').textContent=fmt(s.stop_loss);
  $('tp1').textContent=fmt(s.tp1);$('tp2').textContent=fmt(s.tp2);$('tp3').textContent=fmt(s.tp3);
  $('stopStage').textContent=s.stop_stage||'ORIGINAL';
  const tp=Number(s.highest_tp||0);$('tpProgress').style.width=`${Math.min(100,tp/3*100)}%`;
  $('signalMeta').textContent=`Confidence: ${s.confidence||'–'} · Létrehozva: ${dateFmt(s.created_at)}`;
 }else{$('signalStatus').textContent='NINCS';$('signalStatus').className='pill neutral'}

 const a=data.statistics.all_time,t=data.statistics.today;
 $('signals').textContent=a.signals;$('todaySignals').textContent=`Ma: ${t.signals}`;
 $('winRate').textContent=`${Number(a.win_rate||0).toFixed(1)}%`;$('winsLosses').textContent=`${a.wins} win / ${a.losses} loss`;
 $('netR').textContent=`${Number(a.net_r||0).toFixed(2)}R`;$('avgR').textContent=`Átlag: ${Number(a.average_rr||0).toFixed(2)}R`;
 $('profitFactor').textContent=Number(a.profit_factor||0).toFixed(2);$('breakeven').textContent=`Breakeven: ${a.breakeven}`;
 const total=Math.max(1,Number(a.signals||0));
 [['tp1',a.tp1_hits],['tp2',a.tp2_hits],['tp3',a.tp3_hits]].forEach(([id,val])=>{$(id+'Hits').textContent=val;$(id+'Bar').style.width=`${Math.min(100,Number(val||0)/total*100)}%`});

 const body=$('historyBody');body.innerHTML='';
 if(!data.history.length){body.innerHTML='<tr><td colspan="7" class="empty">Még nincs lezárt trade.</td></tr>';return}
 data.history.forEach(x=>{
  const tr=document.createElement('tr');const r=(x.result||x.status||'–').toUpperCase();
  tr.innerHTML=`<td>${dateFmt(x.completed_at||x.created_at)}</td><td><b>${x.symbol||'–'}</b></td><td>${x.direction||'–'}</td><td class="result ${clsResult(r)}">${r}</td><td>TP${x.highest_tp||0}</td><td>${fmt(x.entry_price)}</td><td>${fmt(x.exit_price)}</td>`;
  body.appendChild(tr);
 });
}
async function load(){try{const r=await fetch('/api/dashboard',{cache:'no-store'});if(!r.ok)throw new Error(r.status);render(await r.json())}catch(e){$('botStatus').textContent='DASHBOARD HIBA';$('botDot').className='dot offline';console.error(e)}}
load();setInterval(load,5000);
