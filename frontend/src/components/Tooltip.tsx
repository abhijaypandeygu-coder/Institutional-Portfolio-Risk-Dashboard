import React from 'react';

type Props = {
  children: React.ReactNode;
  text: string;
};

export const Tooltip: React.FC<Props> = ({ children, text }) => (
  <span className="relative group">
    {children}
    <span role="tooltip" className="pointer-events-none absolute hidden group-hover:block group-focus-within:block w-48 p-2 text-sm text-ink bg-subtle rounded shadow-sm -translate-x-1/2 left-1/2 bottom-full mb-2">
      {text}
    </span>
  </span>
);
