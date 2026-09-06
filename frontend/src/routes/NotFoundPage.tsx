import { Link } from "react-router-dom";
import { Card } from "../components/Card";

export function NotFoundPage() {
  return (
    <Card className="px-4 py-6">
      <h2 className="text-sm font-medium text-ink">Page not found</h2>
      <p className="mt-1.5 text-[13px] text-muted">
        That route does not exist.{" "}
        <Link to="/game" className="underline underline-offset-2 hover:text-ink">
          Back to the game viewer
        </Link>
        .
      </p>
    </Card>
  );
}
