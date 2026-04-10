import { render } from "@testing-library/react-native";
import PulsingDots from "@/components/PulsingDots";

describe("PulsingDots", () => {
  it("renders three dots", () => {
    const { getAllByTestId } = render(<PulsingDots color="#2a9d8f" />);
    const dots = getAllByTestId("pulsing-dot");
    expect(dots).toHaveLength(3);
  });

  it("applies the provided color to all dots", () => {
    const testColor = "#2a9d8f";
    const { getAllByTestId } = render(<PulsingDots color={testColor} />);
    const dots = getAllByTestId("pulsing-dot");
    dots.forEach((dot) => {
      expect(dot.props.style.backgroundColor).toBe(testColor);
    });
  });

  it("renders with custom size and spacing", () => {
    const { getAllByTestId } = render(<PulsingDots color="#2a9d8f" size={12} spacing={16} />);
    const dots = getAllByTestId("pulsing-dot");
    expect(dots).toHaveLength(3);
    dots.forEach((dot) => {
      expect(dot.props.style.width).toBe(12);
      expect(dot.props.style.height).toBe(12);
      expect(dot.props.style.borderRadius).toBe(6);
    });
  });
});
