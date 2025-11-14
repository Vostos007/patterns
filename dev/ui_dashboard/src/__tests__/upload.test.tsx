import { render, screen } from "@testing-library/react";

import UploadPanel from "@/components/upload-panel";

test("renders upload button", () => {
  render(<UploadPanel />);
  expect(screen.getByRole("button", { name: /upload document/i })).toBeInTheDocument();
});
