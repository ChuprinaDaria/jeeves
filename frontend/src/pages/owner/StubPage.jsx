const StubPage = ({ title }) => (
  <div className="max-w-3xl">
    <h1 className="text-3xl font-semibold text-ink mb-4">{title}</h1>
    <div className="bg-paper border border-ink/10 rounded-sm p-8">
      <p className="text-ink/70">
        This section is coming soon. It will be built in a future
        implementation step.
      </p>
    </div>
  </div>
);

export default StubPage;
