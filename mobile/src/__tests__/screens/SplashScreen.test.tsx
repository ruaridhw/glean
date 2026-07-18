import { render } from "@testing-library/react-native";
import SplashScreen from "@/screens/SplashScreen";

beforeEach(() => jest.useFakeTimers());
afterEach(() => jest.useRealTimers());

describe("SplashScreen", () => {
  it("renders the app background color", () => {
    const { getByTestId } = render(<SplashScreen />);
    const container = getByTestId("splash-container");
    expect(container.props.style.backgroundColor).toBe("#2e9d63");
  });

  it("renders the logo image", () => {
    const { getByTestId } = render(<SplashScreen />);
    const logo = getByTestId("splash-logo");
    expect(logo).toBeDefined();
  });

  it("renders the PulsingDots component", () => {
    const { getByTestId } = render(<SplashScreen />);
    const dots = getByTestId("pulsing-dots-container");
    expect(dots).toBeDefined();
  });

  it("centers content vertically and horizontally", () => {
    const { getByTestId } = render(<SplashScreen />);
    const container = getByTestId("splash-container");
    expect(container.props.style.justifyContent).toBe("center");
    expect(container.props.style.alignItems).toBe("center");
  });
});
