/* global React, ReactDOM, Sidebar, TopBar, Painel, Monitors, Alerts, ProductDetail, NotificationsPanel, AddProductModal, Icon */
// Orquestrador da UI estatica: mantem navegacao, modais e dados em memoria.
// Consumido diretamente pelo bootstrap em index.html depois de todos os globais.

function LoadingScreen() {
  return (
    <div className="ma-loading" style={{minHeight: '100vh'}}>
      <div className="ma-spinner"/>
      <div style={{fontSize: 13, color: 'var(--ma-fg-muted)'}}>Carregando dados…</div>
    </div>
  );
}

function App() {
  const [screen, setScreen] = React.useState('dashboard');
  const [openProductId, setOpenProductId] = React.useState(null);
  const [productDetail, setProductDetail] = React.useState(null);
  const [loadingDetail, setLoadingDetail] = React.useState(false);
  const [notifOpen, setNotifOpen] = React.useState(false);
  const [addOpen, setAddOpen] = React.useState(false);

  const [data, setData] = React.useState({ products: [], notifications: [], loaded: false });

  const loadDashboard = React.useCallback(async () => {
    try {
      const result = await window.MA_API.loadDashboard();
      setData({ ...result, loaded: true });
    } catch (e) {
      console.error('Failed to load dashboard:', e);
      setData(prev => ({ ...prev, loaded: true }));
    }
  }, []);

  React.useEffect(() => {
    loadDashboard();
    // Auto-refresh leve: a API continua sendo a fonte de verdade; a UI apenas reconsulta.
    const interval = setInterval(loadDashboard, 30000);
    return () => clearInterval(interval);
  }, [loadDashboard]);

  const navTo = (s) => { setScreen(s); setOpenProductId(null); setProductDetail(null); };
  // Navegacao global usada por componentes carregados sem import/export.
  window.MA_NAV = navTo;

  const openProduct = React.useCallback(async (id) => {
    setOpenProductId(id);
    setLoadingDetail(true);
    setProductDetail(null);
    try {
      const detail = await window.MA_API.loadProductDetail(id);
      setProductDetail(detail);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const refreshDetail = React.useCallback(async () => {
    if (!openProductId) return;
    const detail = await window.MA_API.loadProductDetail(openProductId);
    setProductDetail(detail);
    loadDashboard();
  }, [openProductId, loadDashboard]);

  const urgentCount = data.products.filter(p => p.latest_comparison?.status === 'urgent').length;

  const screenLabel =
    // Marcador auxiliar de tela para CSS/debug, sem participar da regra de negocio.
    openProductId ? '04 Product detail'
    : screen === 'dashboard' ? '01 Painel'
    : screen === 'monitors' ? '02 Monitoramento'
    : screen === 'alerts' ? '03 Alertas'
    : '00 Unknown';

  if (!data.loaded) return <LoadingScreen/>;

  return (
    <div className="ma-app" data-screen-label={screenLabel}>
      <Sidebar
        screen={openProductId ? 'monitors' : screen}
        setScreen={navTo}
        alertsCount={urgentCount}
        products={data.products}
        nextCollect={null}/>
      <div className="ma-main">
        <TopBar
          openNotifications={() => setNotifOpen(true)}
          openAddProduct={() => setAddOpen(true)}
          alertsCount={urgentCount}/>
        <main className="ma-content">
          {openProductId && (
            loadingDetail ? (
              <div className="ma-loading">
                <div className="ma-spinner"/>
                <div>Carregando produto…</div>
              </div>
            ) : productDetail ? (
              <ProductDetail
                product={productDetail}
                onBack={() => { setOpenProductId(null); setProductDetail(null); }}
                onRefresh={refreshDetail}/>
            ) : (
              <div className="ma-loading">
                <Icon name="warning" size={24} color="var(--ma-fg-subtle)"/>
                <div>Produto não encontrado.</div>
              </div>
            )
          )}
          {!openProductId && screen === 'dashboard' && (
            <Painel
              products={data.products}
              notifications={data.notifications}
              onOpen={openProduct}
              onAdd={() => setAddOpen(true)}
              onAllAlerts={() => navTo('alerts')}/>
          )}
          {!openProductId && screen === 'monitors' && (
            <Monitors
              products={data.products}
              onOpen={openProduct}
              onAdd={() => setAddOpen(true)}/>
          )}
          {!openProductId && screen === 'alerts' && (
            <Alerts
              notifications={data.notifications}
              products={data.products}
              onOpen={openProduct}/>
          )}
        </main>
      </div>
      <NotificationsPanel
        open={notifOpen}
        onClose={() => setNotifOpen(false)}
        notifications={data.notifications}
        onOpenProduct={(id) => { setNotifOpen(false); openProduct(id); }}/>
      <AddProductModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onAdded={loadDashboard}/>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
