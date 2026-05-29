return {

	"granular-diff-buffer",

	dir = vim.fn.stdpath("config"),

	init = function()
		local group = vim.api.nvim_create_augroup("NvimAnywhereDiff", { clear = true })

		local ns_id = vim.api.nvim_create_namespace("granular_diff_broken_lines")

		vim.api.nvim_create_autocmd({ "BufReadPost", "TextChanged", "TextChangedI" }, {

			group = group,

			-- SCHRANKE 1: Das Autocmd feuert NUR in diesem Verzeichnis

			pattern = "*/tmp/nvim-anywhere/*",

			callback = function()
				local bufnr = vim.api.nvim_get_current_buf()

				-- Zusätzlicher Check, ob der Dateiname wirklich passt

				local buf_name = vim.api.nvim_buf_get_name(bufnr)

				if not buf_name:find("/tmp/nvim-anywhere/") then
					return
				end

				-- 1. Aktuellen Text aus dem Buffer holen

				local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)

				local current_text = table.concat(lines, "\n")

				-- Schleifenschutz: Wenn die Klammern schon drin sind, abbrechen

				if current_text == "" or current_text:find("%[%-") or current_text:find("%{%+") then
					return
				end

				-- DEIN ORIGINALTEXT

				local original_text = "Ich schreibe jetze ganz schnell einen text"

				local python_script = vim.fn.expand("~/.config/nvim/scripts/build_diff.py")

				-- 2. Python im Hintergrund ausführen

				vim.system({ "python3", python_script, original_text, current_text }, { text = true }, function(obj)
					if obj.code ~= 0 or not obj.stdout or obj.stdout == "" then
						return
					end

					vim.schedule(function()
						-- SCHRANKE 2: Bevor wir irgendwas tun, prüfen wir, ob der User

						-- in der Zwischenzeit das Fenster/die Datei gewechselt hat!

						if not vim.api.nvim_buf_is_valid(bufnr) then
							return
						end

						local active_buf_name = vim.api.nvim_buf_get_name(vim.api.nvim_get_current_buf())

						if not active_buf_name:find("/tmp/nvim-anywhere/") then
							return
						end

						-- 3. Alte Highlights entfernen (Nur in DIESEM Namespace/Buffer)

						vim.api.nvim_buf_clear_namespace(bufnr, ns_id, 0, -1)

						-- 4. Text im Buffer austauschen (Events blockieren!)

						local new_lines = vim.split(obj.stdout, "\n")

						vim.api.nvim_cmd({ cmd = "noautocmd", args = { "lua" } }, {})

						vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, new_lines)

						-- 5. Zeilenweise matchen und einfärben

						for line_idx, line in ipairs(new_lines) do
							local line_num = line_idx - 1

							if line:find("%[%-") then
								-- Zeile ist eine Löschung -> Rot färben

								vim.api.nvim_buf_set_extmark(bufnr, ns_id, line_num, 0, {

									end_col = #line,

									hl_group = "DiffDelete",
								})
							elseif line:find("%{%+") then
								-- Zeile ist eine Hinzufügung -> Grün färben

								vim.api.nvim_buf_set_extmark(bufnr, ns_id, line_num, 0, {

									end_col = #line,

									hl_group = "DiffAdd",
								})
							end
						end
					end)
				end)
			end,
		})
	end,
}
