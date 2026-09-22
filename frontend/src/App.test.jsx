import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import App from "./App.jsx";

const json = (body, status = 200) => Promise.resolve({ ok: status < 400, status, json: async () => body });
const chatReply = (o = {}) => ({ reply: "Check-in is from 3:00 PM.", type: "answer", availability: null, sources: ["checkin"], degraded: false, ...o });
const roomsResult = {
  check_in: "2030-10-01", check_out: "2030-10-03", adults: 3, nights: 2,
  rooms: [{ id: "deluxe", name: "Deluxe Room", capacity: 3, price_per_night: 180, total: 360 }],
};
const bodyOf = (call) => JSON.parse(call[1].body);

beforeEach(() => { global.fetch = vi.fn(); });
afterEach(() => vi.restoreAllMocks());

test("shows a typing indicator while waiting, then the answer", async () => {
  let resolve;
  fetch.mockReturnValue(new Promise((r) => { resolve = r; }));
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: /Our Rooms/i }));
  expect(screen.getByRole("status", { name: /typing/i })).toBeInTheDocument();
  resolve(await json(chatReply()));
  expect(await screen.findByText("Check-in is from 3:00 PM.")).toBeInTheDocument();
  expect(screen.queryByRole("status", { name: /typing/i })).not.toBeInTheDocument();
});

test("follow-up question sends the whole conversation", async () => {
  fetch.mockReturnValueOnce(json(chatReply())).mockReturnValueOnce(json(chatReply({ reply: "Breakfast is 7-10:30." })));
  render(<App />);
  await userEvent.type(screen.getByLabelText("Your question"), "What time is check-in?{enter}");
  await screen.findByText("Check-in is from 3:00 PM.");
  await userEvent.type(screen.getByLabelText("Your question"), "And breakfast?{enter}");
  await screen.findByText("Breakfast is 7-10:30.");
  expect(bodyOf(fetch.mock.calls[1]).messages.map((m) => m.role)).toEqual(["user", "assistant", "user"]);
});

test("availability intent opens the form; submitting shows room cards", async () => {
  fetch
    .mockReturnValueOnce(json(chatReply({ type: "needs_availability_input", reply: "Please give me your dates." })))
    .mockReturnValueOnce(json(roomsResult));
  render(<App />);
  await userEvent.type(screen.getByLabelText("Your question"), "any rooms available?{enter}");
  const form = await screen.findByRole("form", { name: /check availability/i });
  fireEvent.change(screen.getByLabelText("Check-in"), { target: { value: "2030-10-01" } });
  fireEvent.change(screen.getByLabelText("Check-out"), { target: { value: "2030-10-03" } });
  fireEvent.change(screen.getByLabelText("Guests"), { target: { value: "3" } });
  await userEvent.click(screen.getByRole("button", { name: "Search rooms" }));
  expect(await screen.findByText("Deluxe Room")).toBeInTheDocument();
  expect(screen.getByText("$360 total")).toBeInTheDocument();
  expect(bodyOf(fetch.mock.calls[1])).toEqual({ check_in: "2030-10-01", check_out: "2030-10-03", adults: 3 });
  expect(form).not.toBeInTheDocument();
});

test("reversed dates never reach the API", async () => {
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: "Check availability" }));
  fireEvent.change(screen.getByLabelText("Check-in"), { target: { value: "2030-10-03" } });
  fireEvent.change(screen.getByLabelText("Check-out"), { target: { value: "2030-10-01" } });
  await userEvent.click(screen.getByRole("button", { name: "Search rooms" }));
  expect(fetch).not.toHaveBeenCalled();
});

test("server error shows an alert and Try again recovers", async () => {
  fetch.mockReturnValueOnce(json({}, 500)).mockReturnValueOnce(json(chatReply()));
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: /Our Rooms/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/something went wrong/i);
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("Check-in is from 3:00 PM.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("network failure shows a connection message", async () => {
  fetch.mockRejectedValue(new TypeError("Failed to fetch"));
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: /Amenities/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent(/can't reach the server/i);
});

test("degraded answers are labelled as limited mode", async () => {
  fetch.mockReturnValue(json(chatReply({ degraded: true })));
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: /Our Rooms/i }));
  expect(await screen.findByText(/limited mode/i)).toBeInTheDocument();
});
