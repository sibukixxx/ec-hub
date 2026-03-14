import Router from 'preact-router';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { Candidates } from './pages/Candidates';
import { Compare } from './pages/Compare';
import { Messages } from './pages/Messages';
import { Operations } from './pages/Operations';
import { Orders } from './pages/Orders';
import { ProfitCalc } from './pages/ProfitCalc';

export function App() {
  return (
    <div class="layout">
      <Sidebar />
      <main class="main">
        <Router>
          <Dashboard path="/" />
          <Operations path="/operations" />
          <Candidates path="/candidates" />
          <Compare path="/compare" />
          <Messages path="/messages" />
          <Orders path="/orders" />
          <ProfitCalc path="/calc" />
        </Router>
      </main>
    </div>
  );
}
