import { redirect } from 'next/navigation';

// Root → dashboard; oturum yoksa middleware /login'e yönlendirir
export default function RootPage() {
  redirect('/dashboard');
}
