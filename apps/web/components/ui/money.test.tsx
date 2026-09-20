import {render,screen} from '@testing-library/react';
import {describe,expect,it} from 'vitest';
import {Money} from './money';

describe('Money',()=>{
  it('formatea EUR con locale español',()=>{
    render(<Money value="1234.5"/>);
    expect(screen.getByText(/1[.]?234,50/)).toBeInTheDocument();
  });
  it('no muestra NaN para entradas inválidas',()=>{
    render(<Money value="no-es-numero"/>);
    expect(screen.getByText(/0,00/)).toBeInTheDocument();
  });
});
