import { request } from "@/lib/api";
import { definitionSchema } from "@/lib/schemas";
export const definitions = {
  list: () => request("/workflow-definitions", definitionSchema.array()),
};
