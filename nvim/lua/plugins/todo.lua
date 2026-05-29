return {

	"folke/todo-comments.nvim",

	dependencies = { "nvim-lua/plenary.nvim" },

	opts = {

		keywords = {

			DIFF_DEL = {

				icon = " ",

				color = "error",

				alt = { "[[-" },
			},

			DIFF_ADD = {

				icon = " ",

				color = "hint",

				alt = { "{+" },
			},
		},

		highlight = {

			multiline = false,

			-- "wide" sorgt dafür, dass die Klammer selbst vollflächig

			-- als Hintergrundblock eingefärbt wird.

			keyword = "wide",

			-- CRITICAL FIX: Das stand bei dir auf "fg" – das war der Übeltäter!

			-- Wenn es leer "" ist, stoppt das Highlighting SOFORT nach der Klammer

			-- und blutet nicht mehr in die ganze Zeile.

			after = "",

			-- Deine funktionierende Regex bleibt unangetastet:

			pattern = [[\v(\[\[-|\{\+)]],

			comments_only = false,
		},

		colors = {

			error = { "DiagnosticError", "ErrorMsg", "#DC2626" }, -- Rot

			hint = { "DiagnosticHint", "#10B981" }, -- Grün
		},

		search = {

			pattern = [[(KEYWORDS)]],
		},
	},
}
