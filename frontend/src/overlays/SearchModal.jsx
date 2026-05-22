/* global React, Icon, IconButton, MarketplaceChip, StatusDot, inferMarketplace, brl */
// Launcher de navegação: busca local (produtos em memória) + backend (concorrentes).

function SearchModal({ open, onClose, onOpen, onAdd, products }) {
  const [q, setQ]                     = React.useState('');
  const [competitors, setCompetitors] = React.useState([]);
  const [loadingComp, setLoadingComp] = React.useState(false);
  const [activeIdx, setActiveIdx]     = React.useState(0);
  const inputRef    = React.useRef(null);
  const debounceRef = React.useRef(null);

  React.useEffect(() => {
    if (open) {
      setQ(''); setCompetitors([]); setActiveIdx(0); setLoadingComp(false);
      setTimeout(() => inputRef.current?.focus(), 40);
    }
  }, [open]);

  const term = q.trim().toLowerCase();

  // Produtos locais — instant, sem rede.
  const matchedProducts = React.useMemo(() => {
    if (term.length < 1) return [];
    return (products || [])
      .filter(p =>
        (p.name || '').toLowerCase().includes(term) ||
        (p.url_normalized || '').toLowerCase().includes(term)
      )
      .slice(0, 8);
  }, [term, products]);

  // Sugestões de acesso rápido (estado idle): produtos mais ativos.
  const suggestions = React.useMemo(() => {
    return [...(products || [])]
      .sort((a, b) => (b.last_history_ts || 0) - (a.last_history_ts || 0))
      .slice(0, 5);
  }, [products]);

  // Busca no backend apenas para concorrentes, após debounce.
  React.useEffect(() => {
    clearTimeout(debounceRef.current);
    if (term.length < 2) { setCompetitors([]); setLoadingComp(false); return; }
    setLoadingComp(true);
    debounceRef.current = setTimeout(async () => {
      const r = await window.MA_API.search(q);
      setCompetitors((r || []).filter(item => item.type === 'competitor').slice(0, 5));
      setLoadingComp(false);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [term]);

  // Lista plana para navegação por teclado.
  const isSearching    = term.length >= 1;
  const showProducts   = isSearching ? matchedProducts : suggestions;
  const showCompetitors = isSearching ? competitors : [];

  const allItems = [
    ...showProducts.map(p => ({ ...p, _resultType: 'product', monitored_id: p.id })),
    ...showCompetitors,
  ];

  React.useEffect(() => { setActiveIdx(0); }, [term]);

  const handleSelect = (item) => { onOpen(item.monitored_id); onClose(); };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape')    { onClose(); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx(i => Math.min(i + 1, allItems.length - 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setActiveIdx(i => Math.max(i - 1, 0)); }
    if (e.key === 'Enter' && allItems[activeIdx]) { handleSelect(allItems[activeIdx]); }
  };

  const isEmpty = isSearching && matchedProducts.length === 0 && competitors.length === 0 && !loadingComp;

  if (!open) return null;

  // ── Componentes visuais internos ─────────────────────────────────────────────

  const SectionLabel = ({ text, count, separator }) => (
    <div style={{
      padding: '6px 16px 4px', fontSize: 11, fontWeight: 700, letterSpacing: '0.06em',
      textTransform: 'uppercase', color: 'var(--ma-fg-subtle)',
      borderTop: separator ? '1px solid var(--ma-border)' : 'none',
    }}>
      {text}
      {count > 0 && (
        <span style={{marginLeft: 6, fontWeight: 400, letterSpacing: 0, textTransform: 'none', color: 'var(--ma-fg-muted)'}}>
          {count}
        </span>
      )}
    </div>
  );

  const ResultRow = ({ item, flatIdx }) => {
    const isActive    = flatIdx === activeIdx;
    const isProduct   = item._resultType === 'product' || item.type === undefined;
    const price       = item.current_price;
    return (
      <button
        onClick={() => handleSelect(item)}
        onMouseEnter={() => setActiveIdx(flatIdx)}
        style={{
          display: 'grid', gridTemplateColumns: '20px 1fr auto',
          alignItems: 'center', gap: 12, padding: '9px 16px',
          width: '100%', textAlign: 'left', fontFamily: 'inherit',
          background: isActive ? 'var(--ma-neutral-700)' : 'transparent',
          border: 0, borderBottom: '1px solid var(--ma-border)',
          cursor: 'pointer', color: 'var(--ma-fg)',
        }}>
        <Icon
          name={isProduct ? 'package' : 'link'}
          size={14}
          color={isActive ? 'var(--ma-brand-primary)' : 'var(--ma-fg-subtle)'}/>
        <div style={{minWidth: 0}}>
          <div style={{fontSize:13, fontWeight:600, color:'var(--ma-fg-strong)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>
            {item.name || item.url_normalized}
          </div>
          <div style={{fontSize:11, color:'var(--ma-fg-subtle)', fontFamily:'var(--ma-font-mono)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', marginTop:2}}>
            {isProduct
              ? item.url_normalized
              : `Concorrente de: ${item.parent_name || 'produto monitorado'}`}
          </div>
        </div>
        <div style={{display:'flex', alignItems:'center', gap: 6, flexShrink:0}}>
          {price != null && (
            <span style={{fontFamily:'var(--ma-font-mono)', fontSize:12, fontWeight:700, color:'var(--ma-fg-strong)', whiteSpace:'nowrap'}}>
              {brl(price)}
            </span>
          )}
          <StatusDot status={item.status}/>
          <MarketplaceChip marketplace={inferMarketplace(item.url_normalized)} size="sm"/>
        </div>
      </button>
    );
  };

  const productCount = showProducts.length;

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div
      className="ma-modal-mask"
      onClick={onClose}
      style={{alignItems: 'flex-start', paddingTop: 72}}>
      <div
        style={{
          width: '100%', maxWidth: 620,
          background: 'var(--ma-neutral-500)', border: '1px solid var(--ma-border-strong)',
          borderRadius: 'var(--ma-radius-lg)', boxShadow: 'var(--ma-shadow-lg)', overflow: 'hidden',
          animation: 'maPop var(--ma-dur-slow) var(--ma-ease-out)',
        }}
        onClick={e => e.stopPropagation()}>

        {/* Campo de busca */}
        <div style={{display:'flex', alignItems:'center', gap: 12, padding: '12px 16px', borderBottom: '1px solid var(--ma-border)'}}>
          <Icon name="search" size={16} color="var(--ma-fg-muted)"/>
          <input
            ref={inputRef}
            value={q}
            onChange={e => setQ(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Buscar produto ou URL para navegar..."
            style={{flex:1, background:'transparent', border:'none', outline:'none', color:'var(--ma-fg)', fontSize:14, fontFamily:'inherit'}}
          />
          {loadingComp && <div className="ma-spinner" style={{width:14, height:14, borderWidth:2, flexShrink:0}}/>}
          {!loadingComp && q && <IconButton name="x" size="sm" onClick={() => setQ('')} title="Limpar"/>}
          <kbd style={{fontFamily:'var(--ma-font-mono)', fontSize:11, color:'var(--ma-fg-subtle)', border:'1px solid var(--ma-border)', padding:'1px 6px', borderRadius:4, flexShrink:0}}>Esc</kbd>
        </div>

        {/* Conteúdo principal */}
        <div style={{maxHeight: 420, overflowY: 'auto'}}>

          {/* Idle: Acesso rápido */}
          {!isSearching && suggestions.length > 0 && (
            <>
              <SectionLabel text="Acesso rápido" count={0} separator={false}/>
              {suggestions.map((p, i) => (
                <ResultRow key={p.id} item={{...p, _resultType: 'product', monitored_id: p.id}} flatIdx={i}/>
              ))}
            </>
          )}

          {!isSearching && suggestions.length === 0 && (
            <div style={{padding:'14px 16px', color:'var(--ma-fg-subtle)', fontSize:12}}>
              Nenhum produto monitorado ainda.
            </div>
          )}

          {/* Resultados: Produtos */}
          {isSearching && showProducts.length > 0 && (
            <>
              <SectionLabel text="Produtos" count={showProducts.length} separator={false}/>
              {showProducts.map((p, i) => (
                <ResultRow key={p.id} item={{...p, _resultType: 'product', monitored_id: p.id}} flatIdx={i}/>
              ))}
            </>
          )}

          {/* Resultados: Concorrentes (carregando) */}
          {isSearching && term.length >= 2 && loadingComp && showCompetitors.length === 0 && (
            <>
              <SectionLabel text="Concorrentes" count={0} separator={showProducts.length > 0}/>
              <div style={{padding:'10px 16px', display:'flex', alignItems:'center', gap:8, color:'var(--ma-fg-subtle)', fontSize:12}}>
                <div className="ma-spinner" style={{width:12, height:12, borderWidth:2, flexShrink:0}}/>
                Buscando concorrentes…
              </div>
            </>
          )}

          {/* Resultados: Concorrentes */}
          {isSearching && showCompetitors.length > 0 && (
            <>
              <SectionLabel text="Concorrentes" count={showCompetitors.length} separator={showProducts.length > 0}/>
              {showCompetitors.map((c, i) => (
                <ResultRow key={c.id} item={c} flatIdx={productCount + i}/>
              ))}
            </>
          )}

          {/* Nenhum resultado */}
          {isEmpty && (
            <div style={{padding:'20px 16px', display:'flex', flexDirection:'column', alignItems:'center', gap:12, textAlign:'center'}}>
              <div style={{fontSize:13, color:'var(--ma-fg-subtle)'}}>
                Nenhum resultado para <strong style={{color:'var(--ma-fg)'}}>{q}</strong>
              </div>
              {onAdd && (
                <button
                  onClick={() => { onAdd(); onClose(); }}
                  style={{
                    display:'inline-flex', alignItems:'center', gap:6, padding:'7px 14px',
                    background:'transparent', border:'1px solid var(--ma-border)',
                    borderRadius:'var(--ma-radius-md)', cursor:'pointer',
                    fontFamily:'inherit', fontSize:12, color:'var(--ma-brand-primary)',
                  }}>
                  <Icon name="plus" size={13}/>
                  Adicionar produto →
                </button>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

Object.assign(window, { SearchModal });
