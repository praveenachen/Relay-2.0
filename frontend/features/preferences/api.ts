import { json, request } from "@/lib/api";
import { Preferences, preferenceSchema, preferenceInput } from "@/lib/schemas";
export const preferences = {
  get: () => request("/preferences", preferenceSchema),
  save: (value: Preferences) =>
    request(
      "/preferences",
      preferenceSchema,
      json(preferenceInput.parse(value), "PUT"),
    ),
};
