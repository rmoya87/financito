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
  await page.getByRole('combobox').first().selectOption({label:'Cuenta E2E'});
  await page.locator('input[type="file"]').first().setInputFiles({
    name:'e2e.csv',
    mimeType:'text/csv',
    buffer:Buffer.from('Fecha;Concepto;Importe;Moneda;Comercio\n20/09/2026;Compra E2E;-12,34;EUR;E2E Shop\n'),
  });
  await page.getByRole('button',{name:'Importar extracto'}).click();
  await expect(page.getByText(/Insertados: 1/)).toBeVisible();
  await expect(page.getByRole('cell',{name:'Compra E2E',exact:true})).toBeVisible();
});

test('Vault indexa evidencia y conserva cita navegable',async({page})=>{
  await page.goto('/documents/');
  const input=page.getByPlaceholder('Ruta dentro del Financial Knowledge Vault');
  await input.fill('/tmp/financito-e2e/vault/e2e-policy.txt');
  await page.getByRole('button',{name:'Indexar archivo'}).click();
  await expect(page.getByText('e2e-policy.txt')).toBeVisible();
  await page.getByRole('button',{name:/e2e-policy\.txt/}).click();
  await expect(page.getByText('annual_cost')).toBeVisible();
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
  await expect(page.getByText('Alternativa A')).toBeVisible();

  await page.getByRole('combobox').filter({has:page.locator('option:text("Alternativa aplicada…")')}).selectOption({label:'Alternativa A'});
  await page.getByPlaceholder('Impacto esperado (€)').fill('780');
  await page.getByPlaceholder('Impacto observado (€)').fill('700');
  await page.getByPlaceholder('Explicación').fill('Observado E2E');
  await page.getByRole('button',{name:'Guardar resultado'}).click();
  await expect(page.getByText(/"net":-80/)).toBeVisible();
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
  await page.route('**/api/v1/banking/aspsps?country=ES',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({aspsps:[{name:'Mock Bank',country:'ES'}]})}));
  await page.route('**/api/v1/banking/auth**',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({url:'https://bank.example/authorize'})}));
  await page.goto('/banking/');
  await page.getByRole('combobox').selectOption({label:'Mock Bank'});
  await page.getByRole('button',{name:'Autorizar en el banco'}).click();
  const link=page.getByRole('link',{name:'Continuar con la autorización bancaria'});
  await expect(link).toHaveAttribute('href','https://bank.example/authorize');
});


test('todas las rutas principales pasan auditoría WCAG AA automatizada',async({page})=>{
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
