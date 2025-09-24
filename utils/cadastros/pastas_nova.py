import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from utils import store, session
import os

class PastasPadraoTab(ttk.Frame):
    def __init__(self, master, container, add_tab_fn):
        super().__init__(container)
        self.master = master
        self.container = container
        self.add_tab_fn = add_tab_fn
        self.parametros_originais = {}
        self.parametros_atuais = {}
        self.widgets = {}
        self.dirty = False

        self._build_ui()
        self._carregar_parametros()
        self._bind_events()

    def _bind_events(self):
        # Adicione aqui quaisquer eventos que precisam ser vinculados, se houver.
        pass

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill="both", expand=True)

        ttk.Label(main_frame, text="Configuração de Pastas Padrão", font=("Segoe UI", 12, "bold")).pack(pady=(0, 10), anchor="w")
        ttk.Label(main_frame, text="Defina os caminhos das pastas que a aplicação usará como padrão para importar/exportar arquivos.", wraplength=500, justify="left").pack(pady=(0, 15), anchor="w")

        self._linha(main_frame, "pasta_import_remessa", "Pasta de Arquivos para Importar / Converter",
                    "Ao clicar em Conversor XML, o sistema procura arquivos do tipo XML nesta pasta.\nAo clicar em Conversor Bradesco ou BB, o sistema procura arquivos do tipo REM ou TXT nesta pasta.")
        self._linha(main_frame, "pasta_remessa_nasapay", "Pasta para Salvar Remessa Nasapay",
                    "O sistema salvará as remessas BMP geradas nesta pasta.")
        self._linha(main_frame, "pasta_retorno_nasapay", "Pasta para Salvar Retorno Nasapay",
                    "O usuário salvará o retorno BMP nesta pasta que será usada quando o usuário clicar em converter o retorno BMP > Bradesco ou BMP > BB.\nNesta pasta também será salvo o arquivo retorno convertido BMP > Bradesco ou BMP > BB.")
        self._linha(main_frame, "pasta_boleto_pdf", "Pasta para Salvar Boleto PDF Gerado",
                    "Nesta pasta será salvo os boletos gerados em PDF.")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(20, 0), anchor="w")

        ttk.Button(button_frame, text="Salvar", command=self._salvar_parametros).pack(side="left", padx=(0, 10))
        ttk.Button(button_frame, text="Fechar", command=self._fechar_aba).pack(side="left")

    def _linha(self, parent, key, label_text, tooltip_text):
        frame = ttk.Frame(parent)
        frame.columnconfigure(1, weight=1)
        frame.pack(fill="x", pady=5, anchor="w")

        lbl = ttk.Label(frame, text=label_text + ":")
        lbl.grid(row=0, column=0, sticky="w", padx=(0, 5))

        entry = ttk.Entry(frame)
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.widgets[key] = entry

        btn = ttk.Button(frame, text="Procurar", command=lambda: self._selecionar_diretorio(key))
        btn.grid(row=0, column=2)


        tooltip = ToolTip(lbl, tooltip_text)

        entry.bind("<KeyRelease>", self._on_change)

    def _selecionar_diretorio(self, key):
        initial_dir = self.widgets[key].get() or "C:\\nasapay"
        directory = filedialog.askdirectory(initialdir=initial_dir, title=f"Selecionar {self.widgets[key].cget('text')}")
        if directory:
            self.widgets[key].delete(0, tk.END)
            self.widgets[key].insert(0, directory)
            self._on_change()

    def _carregar_parametros(self):
        eid = session.get_empresa_id()
        if not eid:
            messagebox.showwarning("Pastas Padrão", "Nenhuma empresa selecionada. Não é possível carregar pastas.", parent=self.master)
            return

        c = store._connect()
        try:
            r = c.execute("SELECT valor FROM parametros WHERE empresa_id=? AND secao=? AND chave=?", (eid, "pastas", "pastas_config")).fetchone()
            if r and r[0]:
                import json
                self.parametros_originais = json.loads(r[0])
            else:
                self.parametros_originais = {}
        finally:
            c.close()

        self.parametros_atuais = self.parametros_originais.copy()
        for key, entry_widget in self.widgets.items():
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, self.parametros_atuais.get(key, ""))
        self.dirty = False

    def _salvar_parametros(self):
        eid = session.get_empresa_id()
        if not eid:
            messagebox.showwarning("Pastas Padrão", "Nenhuma empresa selecionada. Não é possível salvar pastas.", parent=self.master)
            return

        for key, entry_widget in self.widgets.items():
            self.parametros_atuais[key] = entry_widget.get()

        import json
        parametros_json = json.dumps(self.parametros_atuais)

        c = store._connect()
        try:
            c.execute("INSERT OR REPLACE INTO parametros (empresa_id, secao, chave, valor) VALUES (?, ?, ?, ?)",
                      (eid, "pastas", "pastas_config", parametros_json))
            c.commit()
            messagebox.showinfo("Pastas Padrão", "Pastas padrão salvas com sucesso!", parent=self.master)
            self.parametros_originais = self.parametros_atuais.copy()
            self.dirty = False
            self._fechar_aba(direct=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar pastas padrão: {e}", parent=self.master)
        finally:
            c.close()

    def _on_change(self, *_):
        current_values = {key: widget.get() for key, widget in self.widgets.items()}
        import json
        self.dirty = (json.dumps(current_values, sort_keys=True) != json.dumps(self.parametros_originais, sort_keys=True))

    def _fechar_aba(self, direct=False):
        if self.dirty and not direct:
            if messagebox.askyesno("Pastas Padrão", "Existem alterações não salvas. Deseja salvar antes de fechar?", parent=self.master):
                self._salvar_parametros()
                return
        
        for tab_id in self.container.tabs():
            if self.container.nametowidget(tab_id) == self:
                self.container.forget(tab_id)
                break

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)

    def enter(self, event=None):
        self.x = event.x_root + 20
        self.y = event.y_root + 10
        self.id = self.widget.after(500, self.showtip)

    def leave(self, event=None):
        self.widget.after_cancel(self.id)
        self.hidetip()

    def showtip(self):
        if self.tipwindow or not self.text:
            return
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f" +{self.x}+{self.y}")

        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

def open_pastas_tab(container, add_tab):
    for tab_id in container.tabs():
        if container.tab(tab_id, "text") == "Pastas Padrão":
            container.select(tab_id)
            return

    tab_frame = PastasPadraoTab(container.master, container, add_tab)
    add_tab(tab_frame, text="Pastas Padrão")
    container.select(tab_frame)


