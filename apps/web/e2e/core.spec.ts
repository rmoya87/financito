import {expect,test} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

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

  await page.getByRole('link',{name:'Resumen'}).click();
  await expect(page.getByRole('heading',{name:'Resumen'})).toBeVisible();
  await expect(page.getByText('Liquidez')).toBeVisible();
  await expect(page.getByText('Gasto por categoría')).toBeVisible();
  await expectAccessible(page);
});

test('navegación principal y salud mantienen estructura accesible',async({page})=>{
  await page.goto('/');
  const navigation=page.getByRole('navigation');
  await expect(navigation).toBeVisible();
  await expect(navigation.getByRole('link',{name:'Movimientos'})).toBeVisible();

  await navigation.getByRole('link',{name:'Salud'}).click();
  await expect(page.getByRole('heading',{name:'Configuración y salud'})).toBeVisible();
  await expect(page.getByText(/schema v\d+/)).toBeVisible();
  await expectAccessible(page);
});
