/* global React, Icon, Button */
// Formulario inline para adicionar concorrente sem sair do detalhe do produto.
function AddCompetitorInline({ productId, onAdded }) {
  const [open, setOpen] = React.useState(false);
  const [url, setUrl] = React.useState('');
  const [name, setName] = React.useState('');
  const [saving, setSaving] = React.useState(false);
  const [err, setErr] = React.useState(null);

  const submit = async () => {
    if (!url.trim()) return;
    setSaving(true); setErr(null);
    try {
      // Cadastro de concorrente tambem dispara processamento assincrono no backend.
      const r = await fetch(`/api/v1/monitored/${productId}/competitors`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim(), name: name.trim() || null }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
      setUrl(''); setName(''); setOpen(false);
      onAdded && onAdded();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return <Button kind="primary" leading="plus" size="sm" onClick={() => setOpen(true)}>Adicionar concorrente</Button>;
  }

  return (
    <div style={{display:'flex', alignItems:'center', gap: 8, flexWrap:'wrap'}}>
      <div className={`ma-input ${err ? 'is-error' : ''}`} style={{height: 32, flex: '1 1 260px', minWidth: 200}}>
        <Icon name="link" size={14}/>
        <input value={url} onChange={e => setUrl(e.target.value)} placeholder="URL do concorrente" onKeyDown={e => e.key === 'Enter' && submit()}/>
      </div>
      <div className="ma-input" style={{height: 32, flex: '0 1 160px'}}>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Nome (opcional)" onKeyDown={e => e.key === 'Enter' && submit()}/>
      </div>
      <Button kind="primary" size="sm" leading="check" onClick={submit} disabled={saving}>{saving ? 'Salvando…' : 'Adicionar'}</Button>
      <Button kind="ghost" size="sm" onClick={() => { setOpen(false); setErr(null); }}>Cancelar</Button>
      {err && <span style={{fontSize: 11, color: 'var(--ma-danger)', width: '100%'}}>{err}</span>}
    </div>
  );
}

Object.assign(window, { AddCompetitorInline });
