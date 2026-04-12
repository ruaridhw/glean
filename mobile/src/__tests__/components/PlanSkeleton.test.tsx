import { render } from "@testing-library/react-native";
import { PlanSkeleton } from "@/components/skeletons/PlanSkeleton";

describe("PlanSkeleton", () => {
  it("renders with the plan.skeleton testID", () => {
    const { getByTestId } = render(<PlanSkeleton />);
    expect(getByTestId("plan.skeleton")).toBeDefined();
  });

  it("renders 5 skeleton rows by default", () => {
    const { getAllByTestId } = render(<PlanSkeleton />);
    expect(getAllByTestId("plan.skeleton.row")).toHaveLength(5);
  });

  it("renders the requested number of rows", () => {
    const { getAllByTestId } = render(<PlanSkeleton rows={3} />);
    expect(getAllByTestId("plan.skeleton.row")).toHaveLength(3);
  });
});
