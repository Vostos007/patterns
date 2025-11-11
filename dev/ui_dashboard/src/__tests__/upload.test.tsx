import { render, screen } from "@testing-library/react";
import UploadPanel from "@/components/upload-panel";

describe("UploadPanel", () => {
  it("renders upload button", () => {
    render(<UploadPanel />);
    expect(screen.getByText(/Create Translation Job/i)).toBeInTheDocument();
  });
});
