(() => {
  const drop = document.getElementById('drop'), file = document.getElementById('file'), log = document.getElementById('uploadLog');
  if (!window.IS_ADMIN || !drop) return;

  async function upload(files) {
    if (!files.length) return;
    let changed = false;
    for (const f of files) {
      const line = document.createElement('div');
      line.textContent = t('cap.processing', { file: f.name });
      log.prepend(line);
      const fd = new FormData();
      fd.append('file', f);
      fd.append('server_id', document.getElementById('uploadServer').value);
      try {
        const { results: [r] } = await api('/api/upload', fd);
        if (r.error) { line.className = 'err'; line.textContent = `${f.name}: ${r.error}`; }
        else if (r.duplicate) { line.className = 'muted'; line.textContent = t('cap.dup', { file: f.name, name: r.name }); }
        else {
          changed = true;
          line.className = 'ok';
          line.textContent = t('cap.ok', { file: f.name, name: r.name, s: r.searches, c: r.contracts }) + (r.errors ? t('cap.ok_err', { n: r.errors }) : '') + (r.server ? ` · ${r.server}` : '') + (r.started_at ? ` · ${fmtDate(r.started_at)}` : '');
        }
      } catch (e) { line.className = 'err'; line.textContent = `${f.name}: ${e.message}`; }
    }
    if (changed) setTimeout(() => location.reload(), 1200);
  }

  // Server muss vor dem Upload gewaehlt sein
  const srvSel = document.getElementById('uploadServer');
  const needServer = () => {
    if (srvSel.value) return true;
    toast(t('err.server_missing')); srvSel.focus(); return false;
  };
  drop.addEventListener('click', e => { if (!needServer()) e.preventDefault(); });
  file.addEventListener('change', () => upload([...file.files]));
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', e => { if (needServer()) upload([...e.dataTransfer.files]); });

  document.querySelectorAll('.capture').forEach(el => {
    const id = el.dataset.id, name = el.querySelector('.cap-name').textContent;
    el.querySelector('.move-server')?.addEventListener('change', async e => {
      try { await api(`/api/captures/${id}/server`, { server_id: +e.target.value }); location.reload(); }
      catch (err) { toast(err.message); }
    });
    el.querySelector('.delete').addEventListener('click', async () => {
      if (!confirm(t('cap.confirm_delete', { name }))) return;
      await api(`/api/captures/${id}/delete`, {});
      el.remove(); toast(t('toast.deleted'));
    });
    el.querySelector('.rename').addEventListener('click', async () => {
      const n = prompt(t('cap.new_name'), name);
      if (!n) return;
      await api(`/api/captures/${id}/rename`, { name: n });
      el.querySelector('.cap-name').textContent = n;
    });
  });

  // Server verwalten
  document.querySelectorAll('#serverTable tr[data-id]').forEach(tr => {
    tr.querySelector('.srv-save').addEventListener('click', async () => {
      try {
        await api(`/api/servers/${tr.dataset.id}/update`, { name: tr.querySelector('.srv-name').value, region: tr.querySelector('.srv-region').value });
        toast(t('srv.saved')); setTimeout(() => location.reload(), 600);
      } catch (err) { toast(err.message); }
    });
    tr.querySelector('.srv-del')?.addEventListener('click', async () => {
      try { await api(`/api/servers/${tr.dataset.id}/delete`, {}); location.reload(); } catch (err) { toast(err.message); }
    });
  });
  document.getElementById('newSrvAdd')?.addEventListener('click', async () => {
    try {
      await api('/api/servers', { name: document.getElementById('newSrvName').value, region: document.getElementById('newSrvRegion').value });
      location.reload();
    } catch (err) { toast(err.message); }
  });
})();
