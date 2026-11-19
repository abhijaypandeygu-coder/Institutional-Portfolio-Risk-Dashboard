import React from 'react';

type Props = {
  children: React.ReactNode;
  text: string;
};

export const Tooltip: React.FC<Props> = ({ children, text }) => (
  <span className="relative group">
    {children}
    <span className="absolute hidden group-hover:block w-48 p-2 text-sm text-slate-100 bg-slate-800 rounded shadow-lg -translate-x-1/2 left-1/2 bottom-full mb-2">
      {text}
    </span>
  </span>
);
