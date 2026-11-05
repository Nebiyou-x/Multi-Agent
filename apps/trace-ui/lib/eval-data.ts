// Eval reports are imported directly so the deployed UI is self-contained.
// The JSON files live in reports/evals/ and are bundled at build time; there is
// no filesystem read at request time. Add a new run by dropping the report in
// reports/evals/ and adding an import below.
import eval32fac52f from "@/reports/evals/eval_32fac52f_20261105_105202.json";
import eval4b4b83c1 from "@/reports/evals/eval_4b4b83c1_20261105_105608.json";
import eval76378ca5 from "@/reports/evals/eval_76378ca5_20261105_105201.json";
import evalAb416ce3 from "@/reports/evals/eval_ab416ce3_20261105_105501.json";
import evalD3bd3327 from "@/reports/evals/eval_d3bd3327_20261105_105605.json";

export const EVAL_DATA = [
  {
    name: "eval_32fac52f_20261105_105202",
    data: eval32fac52f,
  },
  {
    name: "eval_4b4b83c1_20261105_105608",
    data: eval4b4b83c1,
  },
  {
    name: "eval_76378ca5_20261105_105201",
    data: eval76378ca5,
  },
  {
    name: "eval_ab416ce3_20261105_105501",
    data: evalAb416ce3,
  },
  {
    name: "eval_d3bd3327_20261105_105605",
    data: evalD3bd3327,
  },
];
