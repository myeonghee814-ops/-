export default function Loading({ message }: { message: string }) {
  return (
    <div className="loading">
      <div className="loading-spinner" />
      <p>{message}</p>
    </div>
  );
}
