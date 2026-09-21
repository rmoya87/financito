import './globals.css';
import type { Metadata } from 'next';
import { Providers } from '@/components/providers';
import { Shell } from '@/components/shell';
export const metadata:Metadata={title:'Financito',description:'Finanzas personales 360º, privadas y locales'};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="es"><head><link rel="icon" type="image/png" href="/financito-logo.png"/><link rel="apple-touch-icon" href="/financito-logo.png"/></head><body><Providers><Shell>{children}</Shell></Providers></body></html>}
