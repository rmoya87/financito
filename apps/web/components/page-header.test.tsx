import {render,screen} from '@testing-library/react';
import {describe,expect,it} from 'vitest';
import {PageHeader} from './page-header';

describe('PageHeader',()=>{
  it('expone un único heading principal y descripción',()=>{
    render(<PageHeader title="Resumen" description="Datos locales"/>);
    expect(screen.getByRole('heading',{level:1,name:'Resumen'})).toBeInTheDocument();
    expect(screen.getByText('Datos locales')).toBeInTheDocument();
  });
});
