/* global React, Icon, Button, IconButton, MarketplaceChip, MARKETPLACE_META */

function inferMarketplace(url) {
  if (!url) return null;
  if (url.includes('mercadolivre') || url.includes('mercadolibre')) return 'mercadolivre';
  if (url.includes('shopee')) return 'shopee';
  if (url.includes('magazineluiza') || url.includes('magalu')) return 'magalu';
  return null;
}

function AddProductModal({ open, onClose, onAdded }) {
  const [url, setUrl] = React.useState('');
  const [name, setName] = React.useState('');
  const [saving, setSaving] = React.useState(false);
  const [err, setErr] = React.useState(null);

  if (!open) return null;

  const marketplace = inferMarketplace(url);
  const supported = !!marketplace;
  const urlEntered = url.trim().length > 0;

  const submit = async () => {
    if (!url.trim()) { setErr('Insira a URL do produto.'); return; }
    setSaving(true); setErr(null);
    try {
      const r = await fetch('/api/v1/monitored/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim(), name: name.trim() || null }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        const detail = j?.detail;
        const msg = (detail && typeof detail === 'object' ? detail.message : detail) || `Erro ${r.status}`;
        throw new Error(msg);
      }
      setUrl(''); setName('');
      onClose();
      onAdded && onAdded();
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => { setUrl(''); setName(''); setErr(null); onClose(); };

  return (
    <div className="ma-modal-mask" onClick={handleClose}>
      <div className="ma-modal" onClick={e => e.stopPropagation()}>
        <div className="ma-modal-head">
          <Icon name="plus" size={16} style={{marginRight: 10, color: 'var(--ma-brand-primary)'}}/>
          <h2>Adicionar produto</h2>
          <div style={{marginLeft: 'auto'}}>
            <IconButton name="x" onClick={handleClose} title="Fechar" size="sm"/>
          </div>
        </div>

        <div className="ma-modal-body">
          <div className="ma-field">
            <div className="ma-field-label">URL do produto</div>
            <div className={`ma-input ${urlEntered && !supported ? 'is-error' : urlEntered && supported ? 'is-focused' : ''}`}>
              <Icon name="link" size={16}/>
              <input
                value={url}
                onChange={e => { setUrl(e.target.value); setErr(null); }}
                placeholder="https://www.mercadolivre.com.br/..."
                onKeyDown={e => e.key === 'Enter' && submit()}
                autoFocus
              />
            </div>
            <div className="ma-field-hint">Marketplaces suportados: Mercado Livre, Shopee, Magalu.</div>
          </div>

          {urlEntered && supported && (
            <div style={{padding: 14, borderRadius: 'var(--ma-radius-md)', background: 'var(--ma-neutral-700)', border: '1px solid var(--ma-border)'}}>
              <div style={{display:'flex', alignItems:'center', gap: 12}}>
                <div style={{width: 44, height: 44, borderRadius: 10, background: 'var(--ma-neutral-500)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink: 0}}>
                  <Icon name="package" size={20} color="var(--ma-fg-muted)"/>
                </div>
                <div style={{flex: 1, minWidth: 0}}>
                  <div style={{display:'flex', alignItems:'center', gap: 8, marginBottom: 4}}>
                    <MarketplaceChip marketplace={marketplace} size="sm"/>
                    <span style={{fontSize: 11, color: 'var(--ma-success)', fontWeight: 700, letterSpacing:'0.06em', textTransform:'uppercase', display:'inline-flex', alignItems:'center', gap: 4}}>
                      <Icon name="check" size={12}/> URL válida
                    </span>
                  </div>
                  <div style={{fontSize: 11, color: 'var(--ma-fg-subtle)', fontFamily:'var(--ma-font-mono)', marginTop: 2}}>
                    primeira coleta enfileirada após salvar
                  </div>
                </div>
              </div>
            </div>
          )}

          {urlEntered && !supported && (
            <div style={{padding: 14, borderRadius: 'var(--ma-radius-md)', background: 'rgba(224,73,73,0.08)', border: '1px solid rgba(224,73,73,0.3)'}}>
              <div style={{display:'flex', alignItems:'flex-start', gap: 12}}>
                <Icon name="warning" size={20} color="var(--ma-danger)" style={{marginTop: 2}}/>
                <div style={{flex: 1, fontSize: 13, color: 'var(--ma-fg)', lineHeight: 1.5}}>
                  <b style={{color: 'var(--ma-fg-strong)'}}>Marketplace não suportado.</b> O <span style={{fontFamily: 'var(--ma-font-mono)'}}>market_scraper</span> só consegue ler URLs de Mercado Livre, Shopee e Magalu. O produto será cadastrado com status <span style={{fontFamily:'var(--ma-font-mono)', color: 'var(--ma-fg-strong)'}}>unsupported</span>.
                </div>
              </div>
            </div>
          )}

          <div className="ma-field">
            <div className="ma-field-label">
              Nome <span style={{textTransform:'none', letterSpacing: 0, color: 'var(--ma-fg-subtle)', fontWeight: 500, marginLeft: 6}}>opcional</span>
            </div>
            <div className="ma-input">
              <Icon name="tag" size={16}/>
              <input
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Usar o nome detectado pelo parser"
                onKeyDown={e => e.key === 'Enter' && submit()}
              />
            </div>
            <div className="ma-field-hint">Deixe em branco para usar o nome lido da página.</div>
          </div>

          <div style={{display:'flex', alignItems:'flex-start', gap: 10, padding: '10px 12px', background: 'rgba(255,196,0,0.06)', borderRadius: 'var(--ma-radius-sm)', border: '1px solid rgba(255,196,0,0.18)'}}>
            <Icon name="zap" size={14} color="var(--ma-brand-secondary)" style={{marginTop: 2, flexShrink: 0}}/>
            <div style={{fontSize: 12, color: 'var(--ma-fg)', lineHeight: 1.5}}>
              A primeira coleta é enfileirada via <span style={{fontFamily:'var(--ma-font-mono)', color:'var(--ma-fg-strong)'}}>enqueue_with_lease</span> e roda logo após salvar. O produto entra com status <span style={{fontFamily:'var(--ma-font-mono)', color:'var(--ma-fg-strong)'}}>pending</span> até a primeira leitura.
            </div>
          </div>

          {err && <div style={{fontSize: 12, color: 'var(--ma-danger)', padding: '8px 12px', background: 'rgba(224,73,73,0.08)', borderRadius: 'var(--ma-radius-sm)', border: '1px solid rgba(224,73,73,0.3)'}}>{err}</div>}
        </div>

        <div className="ma-modal-foot">
          <div style={{flex: 1}}/>
          <Button kind="ghost" onClick={handleClose}>Cancelar</Button>
          <Button kind="primary" leading={saving ? 'refresh' : 'check'} onClick={submit} disabled={saving || !url.trim()}>
            {saving ? 'Adicionando…' : (urlEntered && !supported ? 'Adicionar mesmo assim' : 'Adicionar produto')}
          </Button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AddProductModal });
