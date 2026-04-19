export default function Logo({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      className={className}
      aria-hidden
    >
      <rect x="2" y="2" width="28" height="28" rx="8" fill="currentColor" />
      <path
        d="M10 20.5V11h6.2c2.6 0 4.3 1.5 4.3 3.8 0 1.7-.9 2.9-2.4 3.4l2.9 4.3h-2.9l-2.6-4h-3v4H10zm2.5-6h3.4c1.4 0 2.2-.6 2.2-1.7 0-1.1-.8-1.7-2.2-1.7h-3.4V14.5z"
        fill="white"
      />
    </svg>
  );
}
