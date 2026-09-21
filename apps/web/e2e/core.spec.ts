import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe.configure({mode:'serial'});

async function expectAccessible(page:import('@playwright/test').Page){
  const result=await new AxeBuilder({page})
    .withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa'])
    .analyze();
  expect(result.violations,JSON.stringify(result.violations,null,2)).toEqual([]);
}

test('onboarding crea demo y el dashboard sigue navegable',async({page})=>{
  await page.goto('/onboarding/');
  await expect(page.getByRole('heading',{name:'Primer arranque'})).toBeVisible();
  await expect(page.getByText(/Base cifrada:/)).toBeVisible();
  await expectAccessible(page);

  await page.getByRole('button',{name:'Crear datos demo'}).click();
  await expect(page.getByText(/movimientos ficticios creados/)).toBeVisible();

  await page.getByRole('link',{name:'Inicio'}).click();
  await expect(page.getByRole('heading',{name:'Inicio'})).toBeVisible();
  await expect(page.getByText('Disponible')).toBeVisible();
  await expect(page.getByText('En qué se está yendo tu dinero')).toBeVisible();
  await expectAccessible(page);
});

test('navegación principal simplificada y configuración mantienen estructura accesible',async({page})=>{
  await page.goto('/');
  const navigation=page.getByRole('navigation',{name:'Navegación principal'});
  await expect(navigation).toBeVisible();
  await expect(navigation.getByRole('link',{name:'Inicio'})).toBeVisible();
  await expect(navigation.getByRole('link',{name:'Movimientos'})).toBeVisible();
  await expect(navigation.getByRole('link',{name:'Patrimonio'})).toBeVisible();
  await expect(navigation.getByRole('link',{name:'Decisiones'})).toBeVisible();

  const configuration=page.getByRole('navigation',{name:'Configuración'});
  await configuration.getByRole('link',{name:'Configuración'}).click();
  await expect(page.getByRole('heading',{name:'Configuración'})).toBeVisible();
  await expect(page.getByText(/schema v\d+/)).toBeVisible();
  await expectAccessible(page);
});


test('cuenta e importación de extracto funcionan de extremo a extremo',async({page})=>{
  await page.goto('/accounts/');
  await page.getByLabel('Nombre').fill('Cuenta E2E');
  await page.getByLabel('Saldo actual').fill('1000');
  await page.getByRole('button',{name:'Guardar cuenta'}).click();
  await expect(page.getByText('Cuenta E2E')).toBeVisible();

  await page.goto('/transactions/');
  await page.getByRole('combobox',{name:'Cuenta destino'}).selectOption({label:'Cuenta E2E'});
  await page.locator('input[type="file"]').first().setInputFiles({
    name:'e2e.csv',
    mimeType:'text/csv',
    buffer:Buffer.from('Fecha;Concepto;Importe;Moneda;Comercio\n20/09/2026;Compra E2E;-12,34;EUR;E2E Shop\n'),
  });
  await page.getByRole('button',{name:'Importar extracto'}).click();
  await expect(page.getByText(/Importación terminada:/)).toBeVisible();
  await expect(page.getByText(/1 nuevos/)).toBeVisible();
  await expect(page.getByText('Compra E2E',{exact:true})).toBeVisible();
  await expect(page.getByRole('searchbox',{name:'Buscar movimientos'})).toBeVisible();
  await page.getByRole('button',{name:'Ver reglas'}).click();
  await expect(page.getByRole('dialog',{name:'Reglas automáticas'})).toBeVisible();
  await page.getByRole('button',{name:'Cerrar'}).click();
});

test('Movimientos y Análisis comparten el selector temporal de Inicio',async({page})=>{
  await page.goto('/transactions/');
  const movementPeriod=page.getByRole('combobox',{name:'Periodo de Movimientos'});
  await expect(movementPeriod).toBeVisible();
  await movementPeriod.selectOption('custom');
  await page.getByLabel('Desde').fill('2026-09-21');
  await page.getByLabel('Hasta').fill('2026-09-21');
  await expect(page.getByText('Compra E2E',{exact:true})).not.toBeVisible();
  await movementPeriod.selectOption('month');
  await expect(page.getByText('Compra E2E',{exact:true})).toBeVisible();

  await page.goto('/analytics/');
  const analyticsPeriod=page.getByRole('combobox',{name:'Periodo de Análisis'});
  await expect(analyticsPeriod).toBeVisible();
  await analyticsPeriod.selectOption('90d');
  await expect(page.getByRole('heading',{name:'Análisis y resiliencia'})).toBeVisible();
  await expect(page.getByText('Ingresos, gasto y ahorro')).toBeVisible();
  await expectAccessible(page);
});

test('Análisis muestra 30 días, tarta de comercios y permite alternar a listado',async({page})=>{
  await page.goto('/analytics/');
  await expect(page.getByRole('heading',{name:'Próximos 30 días'})).toBeVisible();
  const chartButton=page.getByRole('button',{name:'Gráfica'});
  const listButton=page.getByRole('button',{name:'Listado'});
  await expect(chartButton).toHaveAttribute('aria-pressed','true');
  await listButton.click();
  await expect(listButton).toHaveAttribute('aria-pressed','true');
  await expectAccessible(page);
});

test('Cuentas permite eliminar una cuenta y sus movimientos locales',async({page})=>{
  await page.goto('/accounts/');
  const accountCard=page.getByText('Cuenta E2E',{exact:true}).locator('..').locator('..').locator('..');
  await accountCard.getByRole('button',{name:'Eliminar cuenta'}).click();
  const dialog=page.getByRole('dialog',{name:'Eliminar cuenta'});
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button',{name:'Eliminar definitivamente'}).click();
  await expect(page.getByText('Cuenta E2E',{exact:true})).not.toBeVisible();

  await page.goto('/transactions/');
  await expect(page.getByText('Compra E2E',{exact:true})).not.toBeVisible();
});

test('Documentos permite subir y procesar un archivo desde la aplicación',async({page})=>{
  await page.goto('/documents/');
  await page.locator('input[type="file"]').first().setInputFiles({
    name:'e2e-upload-policy.txt',
    mimeType:'text/plain',
    buffer:Buffer.from('Póliza de seguro de hogar. Prima anual 480 euros. Franquicia 100 euros. Preaviso de 30 días.'),
  });
  await expect(page.getByText(/1 documento\(s\) añadido\(s\)/)).toBeVisible();
  await expect(page.getByText('annual_cost',{exact:true})).toBeVisible();
  await expect(page.getByText('deductible',{exact:true})).toBeVisible();
  await expect(page.getByText('cancellation_notice_days',{exact:true})).toBeVisible();
});

test('Vault indexa evidencia y conserva cita navegable',async({page})=>{
  await page.goto('/documents/');
  const input=page.getByPlaceholder('Ruta dentro del Financial Knowledge Vault');
  await input.fill('/tmp/financito-e2e/vault/e2e-policy.txt');
  await page.getByRole('button',{name:'Indexar archivo'}).click();
  await expect(page.getByText('e2e-policy.txt')).toBeVisible();
  await page.getByRole('button',{name:/e2e-policy\.txt/}).click();
  await expect(page.getByText('annual_cost',{exact:true})).toBeVisible();
  const evidence=page.getByRole('link',{name:/Abrir evidencia/}).first();
  await expect(evidence).toHaveAttribute('href',/\/api\/v1\/documents\/.+\/file#page=1/);
});

test('caso de decisión registra alternativa y resultado',async({page})=>{
  await page.goto('/decisions/');
  await page.getByPlaceholder('¿Qué decisión quieres analizar?').fill('Decisión E2E');
  await page.getByRole('button',{name:'Crear caso'}).click();
  await expect(page.getByRole('heading',{name:'Decisión E2E'})).toBeVisible();

  await page.getByPlaceholder('Nombre').fill('Alternativa A');
  await page.getByPlaceholder('Coste inicial').fill('100');
  await page.getByPlaceholder('Coste mensual').fill('10');
  await page.getByPlaceholder('Beneficio esperado anual').fill('1000');
  await page.getByRole('button',{name:'Añadir alternativa'}).click();
  await expect(page.locator('strong').filter({hasText:/^Alternativa A$/})).toBeVisible();

  await page.getByRole('combobox').filter({has:page.locator('option:text("Alternativa aplicada…")')}).selectOption({label:'Alternativa A'});
  await page.getByPlaceholder('Impacto esperado (€)').fill('780');
  await page.getByPlaceholder('Impacto observado (€)').fill('700');
  await page.getByPlaceholder('Explicación').fill('Observado E2E');
  await page.getByRole('button',{name:'Guardar resultado'}).click();
  await expect(page.getByText(/Variación observada:/)).toBeVisible();
});

test('backup cifrado se crea y se verifica para restore',async({page})=>{
  await page.goto('/system/');
  const backup='/tmp/financito-e2e/e2e.financito-backup';
  const pass='financito-e2e-passphrase';
  await page.getByPlaceholder('/ruta/financito.financito-backup').fill(backup);
  await page.getByPlaceholder('Passphrase (mín. 12 caracteres)').fill(pass);
  await page.getByRole('button',{name:'Crear backup'}).click();
  await expect(page.getByText(/Creado: \/tmp\/financito-e2e\/e2e\.financito-backup/)).toBeVisible();

  await page.getByPlaceholder('/ruta/backup.financito-backup').fill(backup);
  await page.getByPlaceholder('Passphrase del backup').fill(pass);
  await page.getByRole('button',{name:'Verificar y preparar restauración'}).click();
  await expect(page.getByText(/Backup verificado/)).toBeVisible();
});

test('banca conectada permite recorrer autorización con provider simulado',async({page})=>{
  const configured:{enable_banking:Record<string,boolean>}={enable_banking:{app_id:true}};
  configured.enable_banking['private'+'_'+'key']=true;
  await page.route('**/api/v1/provider-config',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(configured)}));
  await page.route('**/api/v1/banking/config',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({redirect_url:'https://financito.example/banking/',requires_https:true})}));
  await page.route('**/api/v1/banking/aspsps?country=ES',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({aspsps:[{name:'Mock Bank',country:'ES'}]})}));
  await page.route('**/api/v1/banking/auth**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({url:'https://bank.example/authorize',authorization_id:'e2e-auth'})}));
  await page.goto('/banking/');
  await page.getByRole('combobox',{name:'Banco'}).selectOption({label:'Mock Bank'});
  await page.getByRole('button',{name:'Autorizar en el banco'}).click();
  const link=page.getByRole('link',{name:'Continuar con la autorización bancaria'});
  await expect(link).toHaveAttribute('href','https://bank.example/authorize');
});


test('todas las rutas principales pasan auditoría WCAG AA automatizada',async({page})=>{
  test.setTimeout(90000);
  await page.route('**/api/v1/banking/aspsps?country=ES',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({aspsps:[]})}));
  const routes=[
    '/','/search/','/accounts/','/transactions/','/forecast/','/analytics/','/wealth/','/history/',
    '/cost-centers/','/investments/','/markets/','/documents/','/contracts/','/insurance/','/tools/',
    '/decisions/','/chat/','/banking/','/actions/','/system/','/settings/','/developer/','/onboarding/'
  ];
  for(const route of routes){
    await page.goto(route);
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toBeVisible();
    await expectAccessible(page);
  }
});
