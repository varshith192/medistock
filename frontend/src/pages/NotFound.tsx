import { Link } from "react-router-dom";
import { Card, EmptyState } from "../components/ui";

export default function NotFound() {
  return (
    <Card>
      <EmptyState
        title="Page not found"
        description="This page doesn't exist in MediStock 360."
        action={<Link to="/" className="text-[13px] font-medium text-brand-700">Back to overview</Link>}
      />
    </Card>
  );
}
