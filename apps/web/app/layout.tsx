import './globals.css';
import type { Metadata } from 'next';
import { Providers } from '@/components/providers';
import { Shell } from '@/components/shell';
export const metadata:Metadata={title:'Financito',description:'Finanzas personales 360º, privadas y locales'};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="es"><body><Providers><Shell>{children}</Shell></Providers></body></html>}
