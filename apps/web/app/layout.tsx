import './globals.css';
import type { Metadata } from 'next';
import { Providers } from '@/components/providers';
import { Shell } from '@/components/shell';
import {FINANCITO_LOGO_DATA_URI} from '@/lib/brand';
export const metadata:Metadata={title:'Financito',description:'Finanzas personales 360º, privadas y locales'};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="es"><head><link rel="icon" type="image/png" href={FINANCITO_LOGO_DATA_URI}/><link rel="apple-touch-icon" href={FINANCITO_LOGO_DATA_URI}/></head><body><Providers><Shell>{children}</Shell></Providers></body></html>}
