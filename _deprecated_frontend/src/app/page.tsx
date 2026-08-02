import { redirect } from 'next/navigation';

// Root path — always redirect to dashboard (middleware handles auth guard)
export default function RootPage() {
  redirect('/dashboard');
}
