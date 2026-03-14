declare module 'preact-router' {
  import { ComponentType, FunctionComponent } from 'preact';

  export interface RouterProps {
    onChange?: (event: { url: string; previous?: string }) => void;
    children?: preact.ComponentChildren;
  }

  export interface RoutableProps {
    path?: string;
    default?: boolean;
  }

  const Router: FunctionComponent<RouterProps>;
  export default Router;

  export function getCurrentUrl(): string;
  export function route(url: string, replace?: boolean): boolean;
  export function Route(props: {
    component: ComponentType;
    path: string;
    default?: boolean;
  }): preact.VNode;
}
