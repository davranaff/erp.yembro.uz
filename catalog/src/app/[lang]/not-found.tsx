import { Link } from "@/i18n/routing";

export default function NotFound() {
  return (
    <section className="section">
      <div className="container" style={{ textAlign: "center" }}>
        <h1 className="h1" style={{ marginBottom: 16 }}>404</h1>
        <p className="lead" style={{ marginBottom: 32 }}>
          Страница не найдена / Sahifa topilmadi / Page not found
        </p>
        <Link href="/" className="btn btn-primary">
          ←
        </Link>
      </div>
    </section>
  );
}
