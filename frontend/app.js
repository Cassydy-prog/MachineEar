'use strict';
const $=id=>document.getElementById(id), en=document.documentElement.lang==='en';
const t=(fr,english)=>en?english:fr, language=en?'en':'fr';
let file=null,url=null,duration=null,current=null,busy=false;
const labels={fan:t('Ventilateur','Fan'),pump:t('Pompe','Pump'),unknown:t('Non identifié','Unidentified')};
async function api(path,options={}){const res=await fetch(path,options);if(!res.ok){let body;try{body=await res.json();}catch{}throw Error(typeof body?.detail==='string'?body.detail:t('Requête impossible. Vérifie le serveur FastAPI.','Request failed. Check the FastAPI server.'));}return res.json();}
function error(e){$('file-error').textContent=e.message;$('file-error').scrollIntoView({behavior:'smooth',block:'center'});}
function ready(){ $('analyze').disabled=busy||!file||duration===null||duration<2; }
function linkSources(container, record) {
  if (!record) return;

  const sources = record.analysis?.retrieval?.results || [];
  const walker = document.createTreeWalker(
    container,
    NodeFilter.SHOW_TEXT
  );

  const nodes = [];

  while (walker.nextNode()) {
    const node = walker.currentNode;

    // Ne pas modifier les liens ou blocs de code déjà présents.
    if (!node.parentElement.closest('a, code, pre')) {
      nodes.push(node);
    }
  }

  for (const node of nodes) {
    // Reconnaît [Source 1] et 【source 1】, y compris les espaces insécables.
    const pattern = /(?:\[|【|\()\s*source\s*(\d+)\s*(?:\]|】|\))/gi;
    const text = node.textContent;
    const fragment = document.createDocumentFragment();
    let previous = 0;
    let changed = false;

    for (const match of text.matchAll(pattern)) {
      fragment.append(
        document.createTextNode(text.slice(previous, match.index))
      );

      const number = Number(match[1]);
      const source = sources[number - 1];

      if (source) {
        const link = document.createElement('a');
        const page = Number(source.pdf_page_number);
        const pageAnchor =
          Number.isInteger(page) && page > 0 ? `#page=${page}` : '';

        link.href =
          `/api/analyses/${record.id}/sources/${number}${pageAnchor}`;
        link.textContent = `[Source ${number}]`;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'source-link';
        link.title = source.citation || `Source ${number}`;

        fragment.append(link);
      } else {
        // Une citation inconnue ne reçoit aucun lien inventé.
        fragment.append(document.createTextNode(match[0]));
      }

      previous = match.index + match[0].length;
      changed = true;
    }

    if (changed) {
      fragment.append(document.createTextNode(text.slice(previous)));
      node.replaceWith(fragment);
    }
  }
}
function message(text, role = 'assistant') {
  const row = document.createElement('div');
  row.className =
    'message ' + (role === 'user' ? 'user-message' : 'assistant-message');

  const bubble = document.createElement('div');

  // Conserve l’apparence des bulles définie dans le CSS actuel.
  Object.assign(bubble.style, {
    minWidth: '0',
    maxWidth: '100%',
    padding: '13px',
    borderRadius: '13px',
    background: role === 'user' ? '#e2f4f5' : '#f3f5f8',
    fontSize: '12px',
    lineHeight: '1.8',
    overflowWrap: 'anywhere'
  });

  if (
    role === 'assistant' &&
    window.marked &&
    window.DOMPurify
  ) {
    bubble.classList.add('markdown-content');
    bubble.style.overflowX = 'auto';
    bubble.innerHTML = window.DOMPurify.sanitize(
      window.marked.parse(String(text), { breaks: true })
    );
  } else {
    // Affichage sûr si les bibliothèques ne sont pas encore chargées.
    bubble.style.whiteSpace = 'pre-wrap';
    bubble.textContent = String(text);
  }
    if (role === 'assistant') {
    linkSources(bubble, current);
    }
  row.append(bubble);
  $('chat-log').append(row);
  $('chat-log').scrollTop = $('chat-log').scrollHeight;
}
function page(history=false){$('analysis-page').hidden=history;$('history-page').hidden=!history;$('new-analysis').classList.toggle('active',!history);$('history-nav').classList.toggle('active',history);if(history)loadHistory();}
function resetResult(){current=null;$('result').hidden=true;$('hero').classList.remove('compact');}
async function select(candidate){if(!candidate||busy)return;resetResult();file=null;duration=null;$('file-error').textContent='';if(url)URL.revokeObjectURL(url);if(!/\.wav$/i.test(candidate.name)||!candidate.size||candidate.size>50*1024*1024){error(Error(t('Ajoute un WAV non vide de moins de 50 Mo.','Upload a non-empty WAV below 50 MB.')));ready();return;}file=candidate;url=URL.createObjectURL(file);$('audio-player').src=url;$('file-name').textContent=file.name;$('file-info').textContent=(file.size/1048576).toFixed(2)+' MB';$('file-preview').hidden=false;$('drop-zone').hidden=true;ready();}
$('audio-file').onchange=e=>select(e.target.files[0]);$('replace-file').onclick=()=>{if(!busy){$('audio-file').value='';$('audio-file').click();}};
$('audio-player').onloadedmetadata=()=>{duration=Number.isFinite($('audio-player').duration)?$('audio-player').duration:null;if(duration!==null)$('file-info').textContent+=' · '+duration.toFixed(1)+' s';ready();};$('audio-player').onerror=()=>{duration=null;error(Error(t('WAV illisible dans le navigateur.','WAV cannot be played in the browser.')));ready();};
for(const ev of ['dragover','dragenter'])$('drop-zone').addEventListener(ev,e=>{e.preventDefault();$('drop-zone').classList.add('dragover');});for(const ev of ['drop','dragleave'])$('drop-zone').addEventListener(ev,e=>{e.preventDefault();$('drop-zone').classList.remove('dragover');});$('drop-zone').addEventListener('drop',e=>{if(e.dataTransfer.files.length===1)select(e.dataTransfer.files[0]);});
function show(record){current=record;const a=record.analysis.audio, q=record.quality;$('result').hidden=false;$('hero').classList.add('compact');$('result').querySelector('.result-banner strong').textContent=a.is_anomaly?t('Anomalie sonore détectée','Unusual sound detected'):t('Aucune anomalie sonore détectée','No unusual sound detected');$('result').querySelector('.result-banner p').textContent=t('Le résultat ne permet pas d’identifier une panne précise. L’absence d’alerte ne garantit pas le bon état de la machine.','This result does not identify a specific fault. No alert does not guarantee machine health.');$('duration-result').textContent=`${a.duration_sec.toFixed(1)} s · ${labels[a.machine_type]} / ${a.machine_id}`;$('result').querySelector('.result-grid>div:nth-child(2) strong').textContent=q.status==='check'?t('À vérifier','Check recording'):t('Aucun problème évident','No obvious issue');const details=$('result').querySelectorAll('details');$('result-notes').textContent=record.notes||t('Non renseignées.','Not provided.');const host=details[1];host.querySelectorAll('p').forEach(x=>x.remove());const note=document.createElement('p');note.textContent=t('Références générales : correspondance avec cet équipement non confirmée.','Generic references: applicability to this equipment is unconfirmed.');host.append(note);const retrieval=record.analysis.retrieval;for(const source of retrieval.results||[]){const p=document.createElement('p');p.textContent=source.citation+'\n'+source.text;host.append(p);}if(!retrieval.results?.length){const p=document.createElement('p');p.textContent=retrieval.status==='unavailable'?t('Recherche documentaire indisponible ; résultat audio conservé.','Document retrieval unavailable; audio result retained.'):t('Aucun passage retrouvé.','No passage retrieved.');host.append(p);}if(q.issues.length){const p=document.createElement('p');p.textContent=q.issues.map(x=>x==='low_level'?t('Niveau sonore faible.','Low recording level.'):t('Pics proches du niveau maximal.','Peaks near full scale.')).join(' ');note.append(document.createElement('br'),p);} $('chat-log').replaceChildren();message(t('Analyse terminée. Tu peux poser une question ou consulter le rapport. Les contrôles de qualité sont heuristiques et ne mesurent pas le bruit de fond.','Analysis complete. Ask a question or view the report. Quality checks are heuristic and do not measure background noise.'));for(const m of record.chat||[])message(m.content,m.role);}
$('analysis-form').onsubmit=async e=>{e.preventDefault();if(busy||!file)return;const family=document.querySelector('input[name="machine"]:checked')?.value;if(!['fan','pump'].includes(family)||!$('machine-id').value||!$('confirmed').checked){document.querySelector('.equipment-settings').open=true;error(Error(t('Choisis une pompe ou un ventilateur et confirme l’appareil entraîné exact.','Choose a fan or pump and confirm the exact trained device.')));return;}busy=true;ready();$('file-error').textContent='';resetResult();$('progress').hidden=false;$('progress').querySelector('h3').textContent=t('Analyse réelle en cours…','Analysing your recording…');$('progress').querySelector('ol').hidden=true;const data=new FormData();data.append('file',file);data.append('machine_type',family);data.append('machine_id',$('machine-id').value);data.append('confirmed','true');data.append('language',language);data.append('notes',$('notes').value);data.append('equipment',$('equipment').value);try{show(await api('/api/analyses',{method:'POST',body:data}));}catch(e){error(e);}finally{busy=false;ready();$('progress').hidden=true;}};
$('notes').maxLength=1000;
$('analysis-form').addEventListener('input',()=>{if(current)resetResult();});
$('chat-form').onsubmit=async e=>{e.preventDefault();const text=$('chat-input').value.trim();if(!text)return;if(!current){message(t('Analyse d’abord un enregistrement pour discuter de ses résultats.','Analyse a recording first to discuss its results.'));return;}const button=$('chat-form').querySelector('button');button.disabled=true;message(text,'user');try{const response=await api(`/api/analyses/${current.id}/chat`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,language})});message(response.reply);$('chat-input').value='';}catch(e){message(e.message);}finally{button.disabled=false;}};
$('suggestions').hidden=true;
async function loadHistory(){try{const records=await api('/api/analyses');$('history-count').textContent=records.length;$('history-list').replaceChildren();if(!records.length)$('history-list').textContent=t('Aucune analyse enregistrée.','No saved analyses.');for(const r of records){const row=document.createElement('article');row.className='history-item';const b=document.createElement('button');b.className='text-button';b.textContent=r.filename+' · '+new Date(r.created_at).toLocaleString(en?'en-GB':'fr-FR');b.onclick=async()=>{try{show(await api('/api/analyses/'+r.id));page(false);}catch(e){error(e);}};row.append(b);$('history-list').append(row);}}catch(e){$('history-list').textContent=e.message;}}
$('history-nav').onclick=()=>page(true);$('new-analysis').onclick=()=>{if(busy)return;if(file&&!confirm(t('Commencer une nouvelle analyse ?','Start a new analysis?')))return;resetResult();file=null;duration=null;if(url)URL.revokeObjectURL(url);$('audio-player').pause();$('audio-player').removeAttribute('src');$('analysis-form').reset();$('audio-file').value='';$('drop-zone').hidden=false;$('file-preview').hidden=true;$('chat-log').replaceChildren();message(t('Ajoute un enregistrement pour commencer.','Upload a recording to get started.'));$('file-error').textContent='';ready();page(false);};
$('report').onclick=()=>{if(current){$('report-body').textContent=current.report;$('report-dialog').querySelector('.badge').textContent=t('Brouillon non validé','Unvalidated draft');$('report-dialog').showModal();}};$('close-dialog').onclick=()=>$('report-dialog').close();$('print-report').onclick=()=>window.print();$('download-pdf').onclick=()=>{if(current)window.location.href=`/api/analyses/${current.id}/report.pdf`;};$('generate-report').onclick=async()=>{if(!current)return;const id=current.id;const button=$('generate-report');button.disabled=true;try{const data=new FormData();data.append('language',language);const res=await api(`/api/analyses/${id}/report`,{method:'POST',body:data});if(current?.id===id){current.report=res.report;$('report-body').textContent=res.report;}}catch(e){alert(e.message);}finally{button.disabled=false;}};
$('technical').onclick=async()=>{if(!current)return;try{const r=await api('/api/analyses/'+current.id);const url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='machineear-'+r.id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(e){error(e);}};
ready();api('/api/health').catch(error);
