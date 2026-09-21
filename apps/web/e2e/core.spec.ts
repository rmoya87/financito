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
  await expect(page.getByText('Cuenta E2E',{exact:true})).toBeVisible();

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

test('el selector global de periodo se conserva entre Movimientos y Análisis',async({page})=>{
  await page.goto('/transactions/');
  const period=page.getByRole('combobox',{name:'Periodo global'});
  await expect(period).toBeVisible();
  await period.selectOption('custom');
  await page.getByLabel('Desde').fill('2026-09-21');
  await page.getByLabel('Hasta').fill('2026-09-21');
  await expect(page.getByText('Compra E2E',{exact:true})).not.toBeVisible();
  await period.selectOption('90d');

  await page.goto('/analytics/');
  await expect(page.getByRole('combobox',{name:'Periodo global'})).toHaveValue('90d');
  await expect(page.getByRole('heading',{name:'Análisis y resiliencia'})).toBeVisible();
  await expect(page.getByText('Ingresos, gasto y ahorro')).toBeVisible();
  await expectAccessible(page);
});

test('Análisis muestra 30 días, tarta de comercios y permite alternar a listado',async({page})=>{
  await page.goto('/analytics/');
  await expect(page.getByRole('heading',{name:'Próximos 30 días'})).toBeVisible();
  const merchantCard=page.getByRole('heading',{name:'Principales comercios'}).locator('..').locator('..').locator('..');
  const chartButton=merchantCard.getByRole('button',{name:'Gráfica'});
  const listButton=merchantCard.getByRole('button',{name:'Listado'});
  await expect(chartButton).toHaveAttribute('aria-pressed','true');
  await listButton.click();
  await expect(listButton).toHaveAttribute('aria-pressed','true');
  await expect(merchantCard.getByText(/e2e shop/i)).toBeVisible();
  const listPercentages=merchantCard.getByText(/^\d+(?:[.,]\d+)?%$/);
  await expect(listPercentages.first()).toBeVisible();
  for(const value of await listPercentages.allTextContents()){
    expect(Number(value.replace('%','').replace(',','.'))).toBeLessThanOrEqual(100);
  }
  await expectAccessible(page);
});

test('Cuentas permite eliminar una cuenta y sus movimientos locales',async({page})=>{
  await page.goto('/accounts/');
  const accountCard=page.getByText('Cuenta E2E',{exact:true}).locator('..').locator('..').locator('..');
  await accountCard.getByRole('button',{name:'Eliminar cuenta'}).click();
  const dialog=page.getByRole('dialog',{name:'Eliminar cuenta'});
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button',{name:'Eliminar definitivamente'}).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator('div.font-semibold').filter({hasText:/^Cuenta E2E$/})).toHaveCount(0);

  await page.goto('/transactions/');
  await expect(page.getByText('Compra E2E',{exact:true})).not.toBeVisible();
});

test('Patrimonio incorpora Casa y permite eliminar otras deudas',async({page})=>{
  await page.goto('/accounts/');
  await page.getByLabel('Nombre').fill('Cuenta Hipoteca E2E');
  await page.getByLabel('Entidad').fill('Hipoteca E2E');
  await page.getByLabel('Saldo actual').fill('2500');
  await page.getByRole('button',{name:'Guardar cuenta'}).click();
  await expect(page.getByText('Cuenta Hipoteca E2E',{exact:true})).toBeVisible();

  await page.goto('/wealth/');
  const wealthNav=page.getByRole('navigation',{name:'Navegación de Patrimonio'});
  const casa=wealthNav.getByRole('link',{name:'Casa'});
  await expect(casa).toBeVisible();
  await casa.click();
  await expect(casa).toHaveAttribute('aria-current','page');
  await expect(page.getByRole('heading',{name:'Vivienda e hipoteca'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Bienes y evolución de valor'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Seguros relacionados con la vivienda'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Seguros y protección'})).toHaveCount(0);

  await page.getByRole('button',{name:'Nueva hipoteca'}).click();
  const newMortgage=page.getByRole('dialog',{name:'Nueva hipoteca'});
  await expect(newMortgage).toBeVisible();
  await newMortgage.getByRole('combobox',{name:'Cuenta bancaria de la hipoteca'}).selectOption({label:'Hipoteca E2E · Cuenta Hipoteca E2E'});
  await newMortgage.getByPlaceholder('Capital pendiente (€)').fill('150000');
  await newMortgage.getByPlaceholder('Cuota mensual (€)').fill('800');
  await newMortgage.getByPlaceholder('TIN actual (%)').fill('2.5');
  await newMortgage.getByPlaceholder('Meses pendientes').fill('240');
  await newMortgage.getByRole('button',{name:'Crear hipoteca'}).click();
  await expect(page.getByText('Hipoteca E2E',{exact:true}).first()).toBeVisible();
  const createdMortgageData=page.getByRole('dialog',{name:'Datos de la hipoteca'});
  await expect(createdMortgageData).toBeVisible();
  await createdMortgageData.getByRole('button',{name:'Cerrar'}).click();

  await page.getByRole('button',{name:'Detalle de la hipoteca'}).click();
  const mortgageData=page.getByRole('dialog',{name:'Datos de la hipoteca'});
  await expect(mortgageData).toBeVisible();
  await expect(mortgageData.getByRole('tab',{name:'General'})).toHaveAttribute('aria-selected','true');
  await expect(mortgageData.getByPlaceholder('Capital pendiente (€)')).toHaveValue('150000.0000');
  await mortgageData.getByRole('tab',{name:'Detalles'}).click();
  await expect(mortgageData.getByRole('heading',{name:'Condiciones y calendario'})).toBeVisible();
  await expect(mortgageData.getByRole('heading',{name:'Documentación'})).toBeVisible();

  await mortgageData.getByRole('button',{name:'Gestionar documentación'}).click();
  const mortgageDocs=page.getByRole('dialog',{name:/Documentos de la hipoteca/});
  await expect(mortgageDocs).toBeVisible();
  await expect(mortgageDocs.getByRole('button',{name:'Añadir documentos'})).toBeVisible();
  await mortgageDocs.locator('input[type="file"]').setInputFiles({
    name:'hipoteca-e2e.txt',
    mimeType:'text/plain',
    buffer:Buffer.from('Hipoteca E2E. Capital pendiente 150000 euros. Cuota mensual 800 euros. TIN 2,5%.'),
  });
  await expect(mortgageDocs.getByText('hipoteca-e2e.txt',{exact:true}).first()).toBeVisible();
  await expect(mortgageDocs.getByRole('link',{name:'Visualizar documento'})).toBeVisible();
  await mortgageDocs.getByRole('button',{name:'Cerrar'}).click();
  await mortgageData.getByRole('button',{name:'Cerrar'}).click();

  const debtCard=page.getByRole('heading',{name:'Otras deudas'}).locator('..');
  await debtCard.getByPlaceholder('Nombre').fill('Deuda E2E');
  await debtCard.getByPlaceholder('Capital pendiente').fill('1234.56');
  await debtCard.getByRole('button',{name:'Añadir deuda'}).click();
  await expect(debtCard.getByText('Deuda E2E',{exact:true})).toBeVisible();
  page.once('dialog',dialog=>dialog.accept());
  const debtRow=debtCard.getByText('Deuda E2E',{exact:true}).locator('..').locator('..');
  await debtRow.getByRole('button',{name:'Eliminar'}).click();
  await expect(debtCard.getByText('Deuda E2E',{exact:true})).not.toBeVisible();
  await expectAccessible(page);
});

test('Movimientos vincula una cuota hipotecaria y solo descuenta capital',async({page})=>{
  await page.goto('/accounts/');
  await page.getByLabel('Nombre').fill('Cuenta Cuota Hipoteca E2E');
  await page.getByLabel('Saldo actual').fill('3000');
  await page.getByRole('button',{name:'Guardar cuenta'}).click();
  await expect(page.getByText('Cuenta Cuota Hipoteca E2E',{exact:true})).toBeVisible();

  await page.goto('/transactions/');
  await page.getByRole('combobox',{name:'Cuenta destino'}).selectOption({label:'Cuenta Cuota Hipoteca E2E'});
  await page.locator('input[type="file"]').first().setInputFiles({
    name:'cuota-hipoteca-e2e.csv',
    mimeType:'text/csv',
    buffer:Buffer.from('Fecha;Concepto;Importe;Moneda;Comercio\n21/09/2026;Cuota Hipoteca Vinculada E2E;-800,00;EUR;Hipoteca E2E\n'),
  });
  await page.getByRole('button',{name:'Importar extracto'}).click();
  await expect(page.getByText('Cuota Hipoteca Vinculada E2E',{exact:true})).toBeVisible();

  await page.getByRole('button',{name:'Opciones de Cuota Hipoteca Vinculada E2E'}).click();
  const mortgageSelect=page.getByRole('combobox',{name:'Hipoteca para Cuota Hipoteca Vinculada E2E'});
  const mortgageOptionValue=await mortgageSelect.locator('option').filter({hasText:'Hipoteca E2E'}).getAttribute('value');
  expect(mortgageOptionValue).toBeTruthy();
  await mortgageSelect.selectOption(mortgageOptionValue!);
  await expect(page.getByText(/Hipoteca · Hipoteca E2E/)).toBeVisible();
  await page.getByRole('button',{name:/Ver reglas/}).click();
  const rulesDialog=page.getByRole('dialog',{name:'Reglas automáticas'});
  await expect(rulesDialog.getByRole('heading',{name:'Vinculaciones automáticas de pagos'})).toBeVisible();
  await expect(rulesDialog.getByText('cuota hipoteca vinculada e2e',{exact:true})).toBeVisible();
  await expect(rulesDialog.getByText(/Concepto exacto → Hipoteca E2E/)).toBeVisible();
  await rulesDialog.getByRole('button',{name:'Cerrar'}).click();

  await page.goto('/wealth/');
  const mortgagePicker=page.getByRole('combobox',{name:'Hipoteca seleccionada'});
  const pickerValue=await mortgagePicker.locator('option').filter({hasText:'Hipoteca E2E'}).getAttribute('value');
  expect(pickerValue).toBeTruthy();
  await mortgagePicker.selectOption(pickerValue!);
  await page.getByRole('button',{name:'Detalle de la hipoteca'}).click();
  const detail=page.getByRole('dialog',{name:'Datos de la hipoteca'});
  await detail.getByRole('tab',{name:'Transacciones'}).click();
  await expect(detail.getByRole('heading',{name:'Transacciones de la hipoteca'})).toBeVisible();
  await expect(detail.getByText(/Cuota Hipoteca Vinculada E2E/)).toBeVisible();
  await expect(detail.getByText(/^Capital:/)).toBeVisible();
  await expect(detail.getByText(/^Interés estimado:/)).toBeVisible();
  await expect(detail.getByText(/^Saldo después:/)).toBeVisible();
  await expectAccessible(page);
  await detail.getByRole('button',{name:'Cerrar'}).click();
});


test('al pulsar un seguro se abre su ficha completa',async({page})=>{
  await page.goto('/insurance/');
  await page.getByRole('button',{name:'Nuevo seguro'}).click();
  const insuranceAccount=page.getByRole('combobox',{name:'Cuenta bancaria del seguro'}).first();
  await insuranceAccount.selectOption({index:1});
  await page.getByPlaceholder('Aseguradora').fill('Seguro E2E');
  await page.getByPlaceholder('Prima anual (€)').fill('480');
  await page.getByPlaceholder('Franquicia (€)').fill('100');
  await page.getByRole('button',{name:'Crear seguro'}).click();
  await expect(page.getByText('Seguro E2E',{exact:true})).toBeVisible();

  await page.getByText('Seguro E2E',{exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Detalle del seguro'});
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('tab',{name:'General'})).toHaveAttribute('aria-selected','true');
  await expect(dialog.getByRole('tab',{name:'Transacciones'})).toBeVisible();
  await expect(dialog.getByRole('tab',{name:'Detalles'})).toBeVisible();
  await dialog.getByRole('tab',{name:'Detalles'}).click();
  await expect(dialog.getByRole('heading',{name:'Condiciones contractuales'})).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Documentación',exact:true})).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Coberturas, límites y exclusiones'})).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Lectura de la documentación'})).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Obligaciones'})).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Riesgos'})).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Oportunidades de optimizar'})).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Productos vinculados'})).toBeVisible();
  await expect(dialog.getByRole('heading',{name:'Puntos para negociar'})).toBeVisible();
  await dialog.getByRole('button',{name:'Editar seguro'}).click();
  await expect(dialog.getByRole('heading',{name:'Editar seguro'})).toBeVisible();
  await dialog.getByPlaceholder('Prima anual (€)').fill('500');
  await dialog.getByRole('button',{name:'Guardar cambios'}).click();
  await expect(dialog.getByRole('heading',{name:'Editar seguro'})).not.toBeVisible();
  await dialog.getByRole('tab',{name:'Detalles'}).click();

  await dialog.getByRole('button',{name:'Gestionar documentación'}).click();
  const policyDocs=page.getByRole('dialog',{name:/Documentos del seguro/});
  await expect(policyDocs).toBeVisible();
  await expect(policyDocs.getByRole('button',{name:'Añadir documentos'})).toBeVisible();
  await policyDocs.locator('input[type="file"]').setInputFiles({
    name:'seguro-e2e.txt',
    mimeType:'text/plain',
    buffer:Buffer.from('Seguro de hogar. Cubre daños por agua. Prima anual 500 euros. Franquicia 100 euros.'),
  });
  await expect(policyDocs.getByText('seguro-e2e.txt',{exact:true}).first()).toBeVisible();
  await expect(policyDocs.getByRole('link',{name:'Visualizar documento'})).toBeVisible();
  await policyDocs.getByRole('button',{name:'Cerrar'}).click();

  await expectAccessible(page);
  await dialog.getByRole('button',{name:'Cerrar'}).click();
  await expect(dialog).not.toBeVisible();
});

test('Movimientos permite vincular un pago a un seguro y verlo en su detalle',async({page})=>{
  await page.goto('/accounts/');
  await page.getByLabel('Nombre').fill('Cuenta Pago Seguro E2E');
  await page.getByLabel('Saldo actual').fill('1000');
  await page.getByRole('button',{name:'Guardar cuenta'}).click();
  await expect(page.getByText('Cuenta Pago Seguro E2E',{exact:true})).toBeVisible();

  await page.goto('/insurance/');
  await page.getByRole('button',{name:'Nuevo seguro'}).click();
  await page.getByRole('combobox',{name:'Cuenta bancaria del seguro'}).first().selectOption({label:'Manual · Cuenta Pago Seguro E2E'});
  await page.getByPlaceholder('Aseguradora').fill('Aseguradora Pagos E2E');
  await page.getByPlaceholder('Prima anual (€)').fill('123.45');
  await page.getByRole('button',{name:'Crear seguro'}).click();
  await expect(page.getByText('Aseguradora Pagos E2E',{exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Conciliación con tus movimientos'})).toHaveCount(0);

  await page.goto('/transactions/');
  await page.getByRole('combobox',{name:'Cuenta destino'}).selectOption({label:'Cuenta Pago Seguro E2E'});
  await page.locator('input[type="file"]').first().setInputFiles({
    name:'seguro-pago-e2e.csv',
    mimeType:'text/csv',
    buffer:Buffer.from('Fecha;Concepto;Importe;Moneda;Comercio\n21/09/2026;Pago Seguro Vinculado E2E;-123,45;EUR;Aseguradora Pagos E2E\n'),
  });
  await page.getByRole('button',{name:'Importar extracto'}).click();
  await expect(page.getByText('Pago Seguro Vinculado E2E',{exact:true})).toBeVisible();

  await page.getByRole('combobox',{name:'Categoría para Pago Seguro Vinculado E2E'}).selectOption({label:'Seguros'});
  await expect(page.getByText(/Categoría aplicada al concepto/)).toBeVisible();
  await page.goto('/insurance/');
  await expect(page.getByRole('heading',{name:'Lectura de los documentos de las pólizas'})).toHaveCount(0);
  const pendingInsurance=page.getByRole('combobox',{name:'Vincular Pago Seguro Vinculado E2E a seguro'});
  await expect(pendingInsurance).toBeVisible();
  await pendingInsurance.selectOption({label:'Aseguradora Pagos E2E · Hogar'});
  await expect(pendingInsurance).not.toBeVisible();

  await page.getByText('Aseguradora Pagos E2E',{exact:true}).click();
  const detail=page.getByRole('dialog',{name:'Detalle del seguro'});
  await detail.getByRole('tab',{name:'Transacciones'}).click();
  await expect(detail.getByRole('heading',{name:'Transacciones del seguro'})).toBeVisible();
  await expect(detail.getByText(/Pago Seguro Vinculado E2E/)).toBeVisible();
  await expect(detail.getByText(/Cuenta Pago Seguro E2E/)).toBeVisible();
  await expect(detail.getByText(/123,45/).first()).toBeVisible();
  await expectAccessible(page);
  await detail.getByRole('button',{name:'Cerrar'}).click();
});


test('Inicio muestra gastos recurrentes validados en Próximamente',async({page})=>{
  await page.route('**/api/v1/dashboard?**',route=>route.fulfill({
    status:200,
    contentType:'application/json',
    body:JSON.stringify({
      period:{start:'2026-09-01',end:'2026-09-21'},
      liquidity:'1000',income:'2000',expenses:'500',savings:'1500',savings_rate:'0.75',
      spending_by_category:[],
      upcoming_commitments:[{
        id:'recurring-e2e:2026-09-25',
        title:'netflix e2e',
        amount:'17.99',
        due_date:'2026-09-25',
        type:'recurring',
        confidence:'0.92',
        basis:'Patrón recurrente detectado en movimientos',
      }],
      actions:[],
    }),
  }));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Próximamente'})).toBeVisible();
  await expect(page.getByText('netflix e2e',{exact:true})).toBeVisible();
  await expect(page.getByText('Recurrente',{exact:true})).toBeVisible();
  await expect(page.getByText(/Patrón recurrente detectado en movimientos/)).toBeVisible();
  await expectAccessible(page);
});

test('Para ti abre Seguros y coberturas en modal sin salir de Inicio',async({page})=>{
  await page.route('**/api/v1/dashboard?**',route=>route.fulfill({
    status:200,
    contentType:'application/json',
    body:JSON.stringify({
      period:{start:'2026-09-01',end:'2026-09-21'},
      liquidity:'0',income:'0',expenses:'0',savings:'0',savings_rate:null,
      spending_by_category:[],
      upcoming_commitments:[],
      actions:[{
        id:'insurance-home-e2e',
        title:'Seguros y coberturas',
        action_type:'insurance_review',
        priority:'high',
        due_date:null,
        status:'pending',
        notes:'Revisar coberturas y condiciones',
        related_entity_type:null,
        related_entity_id:null,
      }],
    }),
  }));

  await page.goto('/');
  await page.getByRole('button',{name:/Seguros y coberturas/}).click();
  const insuranceDialog=page.getByRole('dialog',{name:'Detalle de Seguros y coberturas'});
  await expect(insuranceDialog).toBeVisible();
  await expect(insuranceDialog.getByRole('heading',{name:'Pólizas'})).toBeVisible();
  await insuranceDialog.getByRole('button',{name:/Seguro E2E/}).click();
  await expect(insuranceDialog.getByRole('heading',{name:'Todo lo indicado por la documentación'})).toBeVisible();
  await expect(insuranceDialog.getByRole('heading',{name:'Obligaciones'})).toBeVisible();
  await expect(insuranceDialog.getByRole('heading',{name:'Riesgos'})).toBeVisible();
  await expect(insuranceDialog.getByRole('heading',{name:'Oportunidades de optimizar'})).toBeVisible();
  await expect(insuranceDialog.getByRole('heading',{name:'Productos vinculados'})).toBeVisible();
  await expect(insuranceDialog.getByRole('heading',{name:'Puntos para negociar'})).toBeVisible();
  await expectAccessible(page);
  await insuranceDialog.getByRole('button',{name:'Cerrar'}).click();
  await expect(insuranceDialog).not.toBeVisible();
});

test('Patrimonio permite eliminar directamente un seguro de hogar',async({page})=>{
  await page.goto('/insurance/');
  await page.getByRole('button',{name:'Nuevo seguro'}).click();
  await page.getByRole('combobox',{name:'Cuenta bancaria del seguro'}).first().selectOption({index:1});
  await page.getByPlaceholder('Aseguradora').fill('Seguro Borrar Patrimonio E2E');
  await page.getByPlaceholder('Prima anual (€)').fill('240');
  await page.getByRole('button',{name:'Crear seguro'}).click();
  await expect(page.getByText('Seguro Borrar Patrimonio E2E',{exact:true})).toBeVisible();

  await page.goto('/wealth/');
  const homeInsurance=page.getByRole('heading',{name:'Seguros relacionados con la vivienda'}).locator('..').locator('..').locator('..');
  const targetInsurance=homeInsurance.locator('div.rounded-lg').filter({hasText:'Seguro Borrar Patrimonio E2E'});
  await expect(targetInsurance.getByText('Seguro Borrar Patrimonio E2E',{exact:true})).toBeVisible();
  page.once('dialog',dialog=>dialog.accept());
  await targetInsurance.getByRole('button',{name:'Eliminar seguro'}).click();
  await expect(homeInsurance.getByText('Seguro Borrar Patrimonio E2E',{exact:true})).not.toBeVisible();

  await page.goto('/insurance/');
  await expect(page.getByText('Seguro Borrar Patrimonio E2E',{exact:true})).not.toBeVisible();
});


test('Mercado muestra análisis local arriba y agrupa evolución dentro de Mis activos',async({page})=>{
  await page.goto('/markets/');
  await expect(page.getByRole('heading',{name:'Lectura de tus activos ahora'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Noticias guardadas · selección útil'})).toBeVisible();
  const assets=page.getByRole('heading',{name:'Mis activos'});
  await expect(assets).toBeVisible();
  const body=page.locator('body');
  await expect(body).not.toContainText("429 Too Many Requests");
  await expect(body).not.toContainText("api.gdeltproject.org");
  await expectAccessible(page);
});

test('Documentos permite subir y procesar un archivo desde la aplicación',async({page})=>{
  await page.goto('/documents/');
  await page.locator('input[type="file"]').first().setInputFiles({
    name:'e2e-upload-policy.txt',
    mimeType:'text/plain',
    buffer:Buffer.from('Póliza de seguro de hogar. Prima anual 480 euros. Franquicia 100 euros. Preaviso de 30 días.'),
  });
  await expect(page.getByText(/1 documento\(s\) añadido\(s\)/)).toBeVisible();
  await expect(page.getByRole('heading',{name:'Evidencia extraída'})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Datos por confirmar'})).toBeVisible();
  await expect(page.getByText('annual_cost',{exact:true})).toBeVisible();
  await expect(page.getByText('deductible',{exact:true})).toBeVisible();
  await expect(page.getByText('cancellation_notice_days',{exact:true})).toBeVisible();

  const annualFact=page.getByText('annual_cost',{exact:true}).locator('..').locator('..').locator('..');
  await annualFact.getByRole('button',{name:'Confirmar'}).click();
  await expect(page.getByText('annual_cost',{exact:true})).not.toBeVisible();

  page.once('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'Eliminar documento'}).click();
  await expect(page.getByRole('button',{name:/e2e-upload-policy\.txt/})).toHaveCount(0);
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
