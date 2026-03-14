import { useState, useEffect } from 'preact/hooks';
import { getCurrentUrl, route } from 'preact-router';

const links = [
  { href: '/', label: 'Dashboard' },
  { href: '/operations', label: 'Operations' },
  { href: '/candidates', label: 'Candidates' },
  { href: '/compare', label: 'Price Compare' },
  { href: '/messages', label: 'Messages' },
  { href: '/orders', label: 'Orders' },
  { href: '/calc', label: 'Profit Calc' },
];

export function Sidebar() {
  const [url, setUrl] = useState(getCurrentUrl());

  useEffect(() => {
    const handler = () => setUrl(getCurrentUrl());
    addEventListener('popstate', handler);
    return () => removeEventListener('popstate', handler);
  }, []);

  const navigate = (href) => (e) => {
    e.preventDefault();
    route(href);
    setUrl(href);
  };

  return (
    <aside class="sidebar">
      <h1>ec-hub</h1>
      <nav>
        {links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            class={url === link.href ? 'active' : ''}
            onClick={navigate(link.href)}
          >
            {link.label}
          </a>
        ))}
      </nav>
    </aside>
  );
}
