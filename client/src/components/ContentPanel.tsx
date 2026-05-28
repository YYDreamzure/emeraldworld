import type { WorldSnapshot } from "../types";

export function ContentPanel({ snapshot }: { snapshot: WorldSnapshot }) {
  const blogs = snapshot.blogs ?? [];
  const paper = snapshot.newspaper ?? [];
  const board = snapshot.billboard ?? [];

  return (
    <div className="content-panel">
      <section>
        <h2>Newspaper</h2>
        {paper.length === 0 ? (
          <p className="muted">No editions yet — Reporter publishes when agents blog.</p>
        ) : (
          paper.map((edition, i) => (
            <article key={i} className="paper-edition">
              <h3>{edition.headline}</h3>
              <ul>
                {edition.articles?.map((a, j) => (
                  <li key={j}>
                    <strong>{a.title}</strong> — {a.author}
                  </li>
                ))}
              </ul>
            </article>
          ))
        )}
      </section>
      <section>
        <h2>Blogs</h2>
        {blogs.length === 0 ? (
          <p className="muted">No published blogs yet.</p>
        ) : (
          <ul className="blog-list">
            {blogs.map((b) => (
              <li key={b.id}>
                <h3>{b.title}</h3>
                <small>{b.author}</small>
                <p>{b.content}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h2>Billboard (Orchard Road)</h2>
        {board.length === 0 ? (
          <p className="muted">No posts yet.</p>
        ) : (
          <ul>
            {board.map((p) => (
              <li key={p.id}>
                <strong>{p.author}:</strong> {p.content}
              </li>
            ))}
          </ul>
        )}
      </section>
      {snapshot.weather && (
        <section>
          <h2>Weather</h2>
          <p>{snapshot.weather}</p>
        </section>
      )}
    </div>
  );
}
