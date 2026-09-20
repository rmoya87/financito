import {describe,expect,it} from 'vitest';
import {categoryColor} from './category-colors';

describe('categoryColor',()=>{
  it('mantiene colores estables y distintos para categorías principales',()=>{
    expect(categoryColor('leisure')).not.toBe(categoryColor('sports'));
    expect(categoryColor('vehicle')).not.toBe(categoryColor('transport'));
    expect(categoryColor('groceries')).toBe(categoryColor('groceries'));
  });

  it('asigna un color determinista a categorías futuras',()=>{
    expect(categoryColor('custom-category')).toBe(categoryColor('custom-category'));
  });
});
