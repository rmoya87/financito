import {describe,expect,it} from 'vitest';
import {financialRangeLabel,resolveGlobalDateRange} from './financial-filters';

describe('financial date ranges',()=>{
  const reference=new Date(2026,8,21,12,0,0);

  it('resuelve el mes anterior completo',()=>{
    expect(resolveGlobalDateRange('previous_month','','',reference)).toEqual({
      start:'2026-08-01',
      end:'2026-08-31',
    });
  });

  it('resuelve 30, 90 y 180 días como rangos inclusivos',()=>{
    expect(resolveGlobalDateRange('30d','','',reference)).toEqual({start:'2026-08-23',end:'2026-09-21'});
    expect(resolveGlobalDateRange('90d','','',reference)).toEqual({start:'2026-06-24',end:'2026-09-21'});
    expect(resolveGlobalDateRange('180d','','',reference)).toEqual({start:'2026-03-26',end:'2026-09-21'});
  });

  it('muestra un rango personalizado en un único texto',()=>{
    expect(financialRangeLabel('custom','2026-08-23','2026-09-21')).toMatch(/23.*ago.*21.*sept.*2026/i);
  });
});
