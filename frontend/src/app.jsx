import Router from 'preact-router';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { Candidates } from './pages/Candidates';
import { Orders } from './pages/Orders';
import { ProfitCalc } from './pages/ProfitCalc';

export function App() {
  return (
    <div class="layout">
      <Sidebar />
      <main class="main">
        <Router>
          <Dashboard path="/" />
          <Candidates path="/candidates" />
          <Orders path="/orders" />
          <ProfitCalc path="/calc" />
        </Router>
      </main>
    </div>
  );
}
