# ==========================================
# inventory_system.py
# Sistema de Inventario y Ventas
# ==========================================

import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import hashlib
import time

# --- CONFIGURACIÓN DE CONEXIÓN GLOBAL (NEON) ---
DB_URL = st.secrets["DB_URL"]

def conectar_db():
    return psycopg2.connect(DB_URL)

def inicializar_tablas():
    conn = conectar_db()
    conn.autocommit = True
    cur = conn.cursor()
    
    # 1. Tabla de Productos
    cur.execute('''CREATE TABLE IF NOT EXISTS productos (
        id SERIAL PRIMARY KEY, 
        codigo TEXT UNIQUE NOT NULL, 
        nombre TEXT NOT NULL, 
        categoria TEXT, 
        precio_compra NUMERIC DEFAULT 0.0, 
        precio_venta NUMERIC DEFAULT 0.0, 
        stock_actual INTEGER DEFAULT 0, 
        stock_minimo INTEGER DEFAULT 5,
        proveedor TEXT,
        ubicacion TEXT,
        fecha_registro DATE DEFAULT CURRENT_DATE
    )''')
    
    # 2. Tabla de Ventas
    cur.execute('''CREATE TABLE IF NOT EXISTS ventas (
        id SERIAL PRIMARY KEY, 
        producto_id INTEGER REFERENCES productos(id), 
        cantidad INTEGER NOT NULL, 
        precio_unitario NUMERIC, 
        total_venta NUMERIC, 
        fecha DATE DEFAULT CURRENT_DATE, 
        metodo_pago TEXT DEFAULT 'Efectivo',
        cliente TEXT,
        vendedor TEXT,
        estado TEXT DEFAULT 'Completada',
        factura TEXT,
        observaciones TEXT
    )''')
    
    # 3. Tabla de Compras (Entradas de inventario)
    cur.execute('''CREATE TABLE IF NOT EXISTS compras (
        id SERIAL PRIMARY KEY, 
        producto_id INTEGER REFERENCES productos(id), 
        cantidad INTEGER NOT NULL, 
        costo_unitario NUMERIC, 
        total_compra NUMERIC, 
        fecha DATE DEFAULT CURRENT_DATE, 
        proveedor TEXT,
        factura_compra TEXT,
        estado TEXT DEFAULT 'Recibida',
        observaciones TEXT
    )''')
    
    # 4. Tabla de Usuarios
    cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, 
        nombre TEXT, 
        usuario TEXT UNIQUE, 
        clave TEXT, 
        rol TEXT DEFAULT 'vendedor'
    )''')
    
    # 5. Tabla de Configuración
    cur.execute('''CREATE TABLE IF NOT EXISTS configuracion (
        id SERIAL PRIMARY KEY, 
        nombre_negocio TEXT DEFAULT 'Mi Negocio',
        direccion TEXT,
        telefono TEXT,
        email TEXT,
        iva NUMERIC DEFAULT 0.0,
        moneda TEXT DEFAULT '€'
    )''')
    
    # 6. Tabla de Categorías
    cur.execute('''CREATE TABLE IF NOT EXISTS categorias (
        id SERIAL PRIMARY KEY, 
        nombre TEXT UNIQUE NOT NULL
    )''')
    
    # --- DATOS INICIALES ---
    
    # Insertar usuario admin por defecto
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Administrador', 'admin', 'admin2026', 'admin') ON CONFLICT DO NOTHING")
    
    # Insertar usuario vendedor por defecto
    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES ('Vendedor', 'vendedor', 'vende2026', 'vendedor') ON CONFLICT DO NOTHING")
    
    # Insertar configuración inicial
    cur.execute("INSERT INTO configuracion (nombre_negocio, moneda) VALUES ('Mi Tienda', '€') ON CONFLICT (id) DO NOTHING")
    
    # Insertar categorías base
    categorias_base = ["Electrónica", "Ropa", "Alimentos", "Hogar", "Juguetes", "Herramientas", "Libros", "Deportes"]
    for cat in categorias_base:
        cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", (cat,))
    
    # Añadir columna de stock mínimo si no existe
    try:
        cur.execute("ALTER TABLE productos ADD COLUMN stock_minimo INTEGER DEFAULT 5")
    except Exception:
        pass
    
    try:
        cur.execute("ALTER TABLE productos ADD COLUMN proveedor TEXT")
    except Exception:
        pass
        
    try:
        cur.execute("ALTER TABLE productos ADD COLUMN ubicacion TEXT")
    except Exception:
        pass
    
    # Añadir columna de cliente y vendedor a ventas
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN cliente TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN vendedor TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE ventas ADD COLUMN factura TEXT")
    except Exception:
        pass
        
    conn.close()

# --- CONFIGURACIÓN DE LA INTERFAZ ---
st.set_page_config(page_title="Jacobo Store - Inventario", layout="wide", page_icon="📦")

# --- SISTEMA ANTI-ATASCOS ---
if 'db_ready' not in st.session_state:
    try:
        inicializar_tablas()
        st.session_state['db_ready'] = True
    except Exception as e:
        st.error(f"Error conectando a la base de datos. Detalle: {e}")
        st.stop()

# --- LOGIN ---
if 'u_rol' not in st.session_state:
    st.session_state['u_rol'] = None
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.sidebar.title("🔐 Acceso al Sistema")
    u = st.sidebar.text_input("Usuario")
    p = st.sidebar.text_input("Contraseña", type="password")
    
    if st.sidebar.button("Ingresar"):
        try:
            conn = conectar_db()
            cur = conn.cursor()
            cur.execute("SELECT rol FROM usuarios WHERE usuario=%s AND clave=%s", (u, p))
            resultado = cur.fetchone()
            
            if resultado:
                st.session_state['logged_in'] = True
                st.session_state['u_rol'] = resultado[0]
                conn.close()
                st.rerun()
            else:
                # Intentar con hash (si se usa)
                cur.execute("SELECT rol FROM usuarios WHERE usuario=%s AND clave=%s", 
                           (u, hashlib.sha256(p.encode()).hexdigest()))
                res_cifrado = cur.fetchone()
                if res_cifrado:
                    st.session_state['logged_in'] = True
                    st.session_state['u_rol'] = res_cifrado[0]
                    conn.close()
                    st.rerun()
                else:
                    st.sidebar.error("Usuario o contraseña incorrectos")
                    conn.close()
        except Exception as e:
            st.sidebar.error(f"Error de conexión: {e}")
    
    st.title("📦 Sistema de Inventario y Ventas")
    st.info("👋 Bienvenido. Ingrese sus credenciales en la barra lateral.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Productos", "0")
    with col2:
        st.metric("Ventas Hoy", "€0")
    with col3:
        st.metric("Stock Bajo", "0")
    
    st.stop()

# --- MENÚ Y BOTÓN DE CERRAR ---
st.sidebar.title("📦 Panel de Control")

# Obtener nombre del negocio
try:
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute("SELECT nombre_negocio FROM configuracion WHERE id = 1")
    nombre_neg = cur.fetchone()
    negocio_nombre = nombre_neg[0] if nombre_neg else "Mi Tienda"
    conn.close()
except:
    negocio_nombre = "Mi Tienda"

st.sidebar.markdown(f"### 🏪 {negocio_nombre}")

# Menú según rol
opciones_menu = [
    "🏠 Inicio",
    "📦 Productos",
    "📥 Compras (Entradas)",
    "💳 Ventas (Salidas)",
    "📊 Balance General"
]

if st.session_state.u_rol == "admin":
    opciones_menu.extend(["🏷️ Categorías", "👥 Usuarios", "⚙️ Configuración"])

menu = st.sidebar.radio("Navegación", opciones_menu)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True, type="primary"):
    st.session_state['logged_in'] = False
    st.session_state['u_rol'] = None
    st.rerun()

# ==========================================
# 🏠 INICIO - Dashboard
# ==========================================
if menu == "🏠 Inicio":
    st.subheader("📊 Dashboard General")
    conn = conectar_db()
    
    # Obtener métricas
    total_productos = pd.read_sql("SELECT COUNT(*) FROM productos", conn).iloc[0,0]
    stock_total = pd.read_sql("SELECT SUM(stock_actual) FROM productos", conn).iloc[0,0] or 0
    
    # Ventas totales
    ventas_total = pd.read_sql("SELECT SUM(total_venta) FROM ventas", conn).iloc[0,0] or 0
    
    # Ventas del día
    hoy = datetime.now().date()
    ventas_hoy = pd.read_sql("SELECT SUM(total_venta) FROM ventas WHERE fecha = %s", conn, params=(hoy,)).iloc[0,0] or 0
    
    # Productos con stock bajo
    stock_bajo = pd.read_sql("SELECT COUNT(*) FROM productos WHERE stock_actual <= stock_minimo", conn).iloc[0,0] or 0
    
    # Ganancia total (ventas - costos)
    costo_total_ventas = pd.read_sql("SELECT SUM(cantidad * precio_unitario) FROM ventas", conn).iloc[0,0] or 0
    # Nota: Para calcular ganancia exacta necesitarías el costo de compra de cada producto vendido
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📦 Total Productos", total_productos)
    c2.metric("💰 Ventas Totales", f"{ventas_total:,.2f} €")
    c3.metric("📈 Ventas Hoy", f"{ventas_hoy:,.2f} €", delta=f"{ventas_hoy/total_productos:.2f}€/prod" if total_productos > 0 else None)
    c4.metric("⚠️ Stock Bajo", stock_bajo, delta="Revisar" if stock_bajo > 0 else "OK")
    
    st.markdown("---")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Ventas por Producto (Top 5)")
        top_productos = pd.read_sql("""
            SELECT p.nombre, SUM(v.cantidad) as total_vendido
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            GROUP BY p.nombre
            ORDER BY total_vendido DESC
            LIMIT 5
        """, conn)
        if not top_productos.empty:
            st.bar_chart(data=top_productos.set_index('nombre'))
        else:
            st.info("No hay datos de ventas aún.")
    
    with col2:
        st.subheader("📈 Ventas por Categoría")
        ventas_categoria = pd.read_sql("""
            SELECT p.categoria, SUM(v.total_venta) as total
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            GROUP BY p.categoria
            ORDER BY total DESC
        """, conn)
        if not ventas_categoria.empty:
            st.dataframe(ventas_categoria, use_container_width=True)
        else:
            st.info("No hay datos de ventas aún.")
    
    # Lista de productos con stock bajo
    if stock_bajo > 0:
        st.markdown("---")
        st.warning(f"⚠️ {stock_bajo} producto(s) con stock bajo:")
        productos_bajo = pd.read_sql("""
            SELECT nombre, stock_actual, stock_minimo
            FROM productos
            WHERE stock_actual <= stock_minimo
            ORDER BY stock_actual ASC
        """, conn)
        st.dataframe(productos_bajo, use_container_width=True)
    
    conn.close()

# ==========================================
# 📦 PRODUCTOS
# ==========================================
elif menu == "📦 Productos":
    tabs = st.tabs(["➕ Nuevo Producto", "✏️ Editar Producto", "🔍 Ver Productos"])
    
    conn = conectar_db()
    
    # Obtener categorías para selects
    categorias_df = pd.read_sql("SELECT nombre FROM categorias ORDER BY nombre", conn)
    categorias_lista = categorias_df['nombre'].tolist() if not categorias_df.empty else []
    
    with tabs[0]:  # ➕ Nuevo Producto
        with st.form("form_nuevo_producto"):
            st.subheader("Registrar Nuevo Producto")
            c1, c2 = st.columns(2)
            
            with c1:
                codigo = st.text_input("Código del Producto *", placeholder="Ej: PROD-001")
                nombre = st.text_input("Nombre del Producto *")
                categoria = st.selectbox("Categoría", categorias_lista + ["Nueva..."])
                if categoria == "Nueva...":
                    categoria_nueva = st.text_input("Nombre de nueva categoría")
                    categoria_final = categoria_nueva if categoria_nueva else "Sin categoría"
                else:
                    categoria_final = categoria
            
            with c2:
                precio_compra = st.number_input("Precio de Compra (€)", min_value=0.0, step=0.01)
                precio_venta = st.number_input("Precio de Venta (€)", min_value=0.0, step=0.01)
                stock_inicial = st.number_input("Stock Inicial", min_value=0, step=1)
                stock_minimo = st.number_input("Stock Mínimo de Alerta", min_value=0, value=5, step=1)
            
            proveedor = st.text_input("Proveedor")
            ubicacion = st.text_input("Ubicación en Almacén")
            
            st.caption("* Campos obligatorios")
            
            if st.form_submit_button("💾 Guardar Producto", type="primary"):
                # Validaciones
                if not codigo.strip():
                    st.error("⚠️ El código del producto es obligatorio.")
                elif not nombre.strip():
                    st.error("⚠️ El nombre del producto es obligatorio.")
                else:
                    try:
                        cur = conn.cursor()
                        cat_final = categoria_final if categoria_final != "Nueva..." else "Sin categoría"
                        
                        cur.execute("""
                            INSERT INTO productos 
                            (codigo, nombre, categoria, precio_compra, precio_venta, 
                             stock_actual, stock_minimo, proveedor, ubicacion)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (codigo.upper().strip(), nombre.strip(), cat_final, 
                              precio_compra, precio_venta, stock_inicial, 
                              stock_minimo, proveedor, ubicacion))
                        
                        # Si se creó una nueva categoría, agregarla a la tabla
                        if categoria == "Nueva..." and categoria_nueva.strip():
                            try:
                                cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", 
                                           (categoria_nueva.strip(),))
                            except:
                                pass
                        
                        conn.commit()
                        st.success("✅ Producto registrado exitosamente")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        conn.rollback()
                        if "codigo" in str(e).lower():
                            st.error(f"⚠️ El código '{codigo}' ya está registrado.")
                        else:
                            st.error(f"⚠️ Error: {e}")
    
    with tabs[1]:  # ✏️ Editar Producto
        productos_df = pd.read_sql("SELECT id, codigo, nombre FROM productos ORDER BY nombre", conn)
        
        if not productos_df.empty:
            producto_seleccionado = st.selectbox(
                "Seleccionar Producto a Editar", 
                productos_df['codigo'] + " - " + productos_df['nombre']
            )
            
            if producto_seleccionado:
                codigo_producto = producto_seleccionado.split(" - ")[0]
                producto_data = pd.read_sql(
                    "SELECT * FROM productos WHERE codigo = %s", 
                    conn, 
                    params=(codigo_producto,)
                ).iloc[0]
                
                with st.form("form_editar_producto"):
                    st.subheader(f"Editando: {producto_data['nombre']}")
                    c1, c2 = st.columns(2)
                    
                    with c1:
                        n_nombre = st.text_input("Nombre", value=producto_data['nombre'])
                        n_categoria = st.selectbox("Categoría", categorias_lista + ["Nueva..."], 
                                                  index=categorias_lista.index(producto_data['categoria']) if producto_data['categoria'] in categorias_lista else 0)
                        if n_categoria == "Nueva...":
                            n_categoria_nueva = st.text_input("Nombre de nueva categoría")
                            n_categoria_final = n_categoria_nueva if n_categoria_nueva else "Sin categoría"
                        else:
                            n_categoria_final = n_categoria
                    
                    with c2:
                        n_precio_compra = st.number_input("Precio de Compra (€)", value=float(producto_data['precio_compra'] or 0), step=0.01)
                        n_precio_venta = st.number_input("Precio de Venta (€)", value=float(producto_data['precio_venta'] or 0), step=0.01)
                        n_stock_actual = st.number_input("Stock Actual", value=int(producto_data['stock_actual'] or 0), step=1)
                        n_stock_minimo = st.number_input("Stock Mínimo", value=int(producto_data['stock_minimo'] or 5), step=1)
                    
                    n_proveedor = st.text_input("Proveedor", value=producto_data['proveedor'] or "")
                    n_ubicacion = st.text_input("Ubicación", value=producto_data['ubicacion'] or "")
                    
                    if st.form_submit_button("💾 Actualizar Producto"):
                        try:
                            cur = conn.cursor()
                            cat_final = n_categoria_final if n_categoria_final != "Nueva..." else "Sin categoría"
                            
                            cur.execute("""
                                UPDATE productos SET 
                                    nombre = %s, categoria = %s, precio_compra = %s, 
                                    precio_venta = %s, stock_actual = %s, stock_minimo = %s,
                                    proveedor = %s, ubicacion = %s
                                WHERE codigo = %s
                            """, (n_nombre, cat_final, n_precio_compra, n_precio_venta,
                                  n_stock_actual, n_stock_minimo, n_proveedor, n_ubicacion,
                                  codigo_producto))
                            
                            if n_categoria == "Nueva..." and n_categoria_nueva.strip():
                                try:
                                    cur.execute("INSERT INTO categorias (nombre) VALUES (%s) ON CONFLICT DO NOTHING", 
                                               (n_categoria_nueva.strip(),))
                                except:
                                    pass
                            
                            conn.commit()
                            st.success("✅ Producto actualizado")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"⚠️ Error: {e}")
        else:
            st.info("No hay productos registrados para editar.")
    
    with tabs[2]:  # 🔍 Ver Productos
        st.subheader("📋 Inventario Actual")
        
        # Filtros
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            categoria_filtro = st.selectbox("Filtrar por Categoría", ["Todas"] + categorias_lista)
        with col_f2:
            stock_filtro = st.selectbox("Filtrar por Stock", ["Todos", "Con Stock", "Sin Stock", "Stock Bajo"])
        
        # Construir consulta
        query = "SELECT codigo, nombre, categoria, precio_compra, precio_venta, stock_actual, stock_minimo, proveedor FROM productos"
        condiciones = []
        params = []
        
        if categoria_filtro != "Todas":
            condiciones.append("categoria = %s")
            params.append(categoria_filtro)
        
        if stock_filtro == "Con Stock":
            condiciones.append("stock_actual > 0")
        elif stock_filtro == "Sin Stock":
            condiciones.append("stock_actual = 0")
        elif stock_filtro == "Stock Bajo":
            condiciones.append("stock_actual <= stock_minimo")
        
        if condiciones:
            query += " WHERE " + " AND ".join(condiciones)
        
        query += " ORDER BY nombre"
        
        productos_mostrar = pd.read_sql(query, conn, params=params if params else None)
        
        if not productos_mostrar.empty:
            st.dataframe(productos_mostrar, use_container_width=True)
            
            # Resumen
            total_valor = (productos_mostrar['precio_compra'] * productos_mostrar['stock_actual']).sum()
            total_venta = (productos_mostrar['precio_venta'] * productos_mostrar['stock_actual']).sum()
            
            c1, c2 = st.columns(2)
            c1.metric("💰 Valor de Inventario (Costo)", f"{total_valor:,.2f} €")
            c2.metric("💰 Valor de Inventario (Venta)", f"{total_venta:,.2f} €")
            
            # Botón para descargar
            csv_data = productos_mostrar.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
            st.download_button(
                label="📥 Descargar Inventario", 
                data=csv_data, 
                file_name=f"inventario_{datetime.now().strftime('%Y%m%d')}.csv", 
                mime="text/csv"
            )
        else:
            st.info("No hay productos que coincidan con los filtros seleccionados.")
    
    conn.close()

# ==========================================
# 📥 COMPRAS (Entradas)
# ==========================================
elif menu == "📥 Compras (Entradas)":
    tabs = st.tabs(["➕ Registrar Compra", "📋 Historial de Compras"])
    
    conn = conectar_db()
    
    with tabs[0]:  # ➕ Registrar Compra
        st.subheader("Registrar Entrada de Mercancía (Compra)")
        
        productos_df = pd.read_sql("SELECT id, codigo, nombre, precio_compra FROM productos ORDER BY nombre", conn)
        
        if not productos_df.empty:
            with st.form("form_registrar_compra"):
                c1, c2 = st.columns(2)
                
                with c1:
                    producto_sel = st.selectbox("Seleccionar Producto", 
                                               productos_df['codigo'] + " - " + productos_df['nombre'])
                    producto_id = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['id'].values[0]
                    precio_compra_actual = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['precio_compra'].values[0]
                    
                    cantidad = st.number_input("Cantidad Comprada", min_value=1, step=1)
                    costo_unitario = st.number_input("Costo Unitario (€)", min_value=0.0, value=float(precio_compra_actual or 0), step=0.01)
                
                with c2:
                    total_compra = cantidad * costo_unitario
                    st.metric("Total Compra", f"{total_compra:,.2f} €")
                    proveedor = st.text_input("Proveedor")
                    factura_compra = st.text_input("Número de Factura")
                    fecha_compra = st.date_input("Fecha de Compra", datetime.now().date())
                
                observaciones = st.text_area("Observaciones")
                
                # Mostrar resumen
                st.info(f"📦 Producto: {producto_sel} | Cantidad: {cantidad} | Costo Unitario: {costo_unitario:.2f}€ | Total: {total_compra:.2f}€")
                
                if st.form_submit_button("✅ Registrar Compra", type="primary"):
                    try:
                        cur = conn.cursor()
                        
                        # Registrar compra
                        cur.execute("""
                            INSERT INTO compras 
                            (producto_id, cantidad, costo_unitario, total_compra, fecha, 
                             proveedor, factura_compra, observaciones, estado)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Recibida')
                        """, (producto_id, cantidad, costo_unitario, total_compra, 
                              fecha_compra, proveedor, factura_compra, observaciones))
                        
                        # Actualizar stock del producto
                        cur.execute("""
                            UPDATE productos 
                            SET stock_actual = stock_actual + %s,
                                precio_compra = %s  -- Actualizar precio de compra
                            WHERE id = %s
                        """, (cantidad, costo_unitario, producto_id))
                        
                        conn.commit()
                        st.success(f"✅ Compra registrada exitosamente. Stock actualizado +{cantidad} unidades.")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        conn.rollback()
                        st.error(f"⚠️ Error al registrar compra: {e}")
        else:
            st.warning("⚠️ No hay productos registrados. Registra productos primero.")
    
    with tabs[1]:  # 📋 Historial de Compras
        st.subheader("📋 Historial de Compras")
        
        compras_df = pd.read_sql("""
            SELECT c.*, p.codigo, p.nombre 
            FROM compras c
            JOIN productos p ON c.producto_id = p.id
            ORDER BY c.fecha DESC
        """, conn)
        
        if not compras_df.empty:
            # Filtros
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                fecha_ini = st.date_input("Desde", compras_df['fecha'].min() if not compras_df.empty else datetime.now().date())
            with col_f2:
                fecha_fin = st.date_input("Hasta", compras_df['fecha'].max() if not compras_df.empty else datetime.now().date())
            
            # Aplicar filtros
            compras_df['fecha'] = pd.to_datetime(compras_df['fecha']).dt.date
            compras_filtradas = compras_df[
                (compras_df['fecha'] >= fecha_ini) & 
                (compras_df['fecha'] <= fecha_fin)
            ]
            
            if not compras_filtradas.empty:
                # Mostrar resumen
                total_invertido = compras_filtradas['total_compra'].sum()
                total_unidades = compras_filtradas['cantidad'].sum()
                
                c1, c2 = st.columns(2)
                c1.metric("💰 Total Invertido", f"{total_invertido:,.2f} €")
                c2.metric("📦 Total Unidades Compradas", total_unidades)
                
                st.dataframe(compras_filtradas[['fecha', 'codigo', 'nombre', 'cantidad', 'costo_unitario', 'total_compra', 'proveedor']], 
                           use_container_width=True)
            else:
                st.info("No hay compras en el rango de fechas seleccionado.")
        else:
            st.info("Aún no hay registros de compras.")
    
    conn.close()

# ==========================================
# 💳 VENTAS (Salidas)
# ==========================================
elif menu == "💳 Ventas (Salidas)":
    tabs = st.tabs(["➕ Registrar Venta", "📋 Historial de Ventas"])
    
    conn = conectar_db()
    
    with tabs[0]:  # ➕ Registrar Venta
        st.subheader("Registrar Salida de Mercancía (Venta)")
        
        productos_df = pd.read_sql("SELECT id, codigo, nombre, precio_venta, stock_actual FROM productos ORDER BY nombre", conn)
        
        if not productos_df.empty:
            with st.form("form_registrar_venta"):
                c1, c2 = st.columns(2)
                
                with c1:
                    producto_sel = st.selectbox("Seleccionar Producto", 
                                               productos_df['codigo'] + " - " + productos_df['nombre'] + " (Stock: " + productos_df['stock_actual'].astype(str) + ")")
                    producto_id = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['id'].values[0]
                    precio_venta_actual = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['precio_venta'].values[0]
                    stock_disponible = productos_df[productos_df['codigo'] == producto_sel.split(" - ")[0]]['stock_actual'].values[0]
                    
                    cantidad = st.number_input("Cantidad a Vender", min_value=1, max_value=stock_disponible if stock_disponible > 0 else 0, step=1)
                    precio_unitario = st.number_input("Precio de Venta Unitario (€)", min_value=0.0, value=float(precio_venta_actual or 0), step=0.01)
                
                with c2:
                    total_venta = cantidad * precio_unitario
                    st.metric("Total Venta", f"{total_venta:,.2f} €")
                    metodo_pago = st.selectbox("Método de Pago", ["Efectivo", "Tarjeta", "Transferencia", "Bizum"])
                    cliente = st.text_input("Cliente")
                    factura = st.text_input("Número de Factura")
                    fecha_venta = st.date_input("Fecha de Venta", datetime.now().date())
                    vendedor = st.text_input("Vendedor", value=st.session_state.get('usuario_actual', ''))
                
                observaciones = st.text_area("Observaciones")
                
                # Mostrar resumen
                if cantidad > stock_disponible:
                    st.error(f"⚠️ Stock insuficiente. Disponible: {stock_disponible} unidades.")
                else:
                    st.success(f"✅ Stock disponible: {stock_disponible} unidades. Venta de {cantidad} unidades.")
                    st.info(f"💰 Subtotal: {total_venta:.2f}€")
                
                if st.form_submit_button("✅ Registrar Venta", type="primary"):
                    if cantidad > stock_disponible:
                        st.error("⚠️ No hay suficiente stock para esta venta.")
                    else:
                        try:
                            cur = conn.cursor()
                            
                            # Registrar venta
                            cur.execute("""
                                INSERT INTO ventas 
                                (producto_id, cantidad, precio_unitario, total_venta, fecha, 
                                 metodo_pago, cliente, vendedor, factura, observaciones, estado)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Completada')
                            """, (producto_id, cantidad, precio_unitario, total_venta, 
                                  fecha_venta, metodo_pago, cliente, vendedor, factura, observaciones))
                            
                            # Actualizar stock del producto
                            cur.execute("""
                                UPDATE productos 
                                SET stock_actual = stock_actual - %s
                                WHERE id = %s
                            """, (cantidad, producto_id))
                            
                            conn.commit()
                            st.success(f"✅ Venta registrada exitosamente. Stock actualizado -{cantidad} unidades.")
                            time.sleep(1)
                            st.rerun()
                            
                        except Exception as e:
                            conn.rollback()
                            st.error(f"⚠️ Error al registrar venta: {e}")
        else:
            st.warning("⚠️ No hay productos registrados. Registra productos primero.")
    
    with tabs[1]:  # 📋 Historial de Ventas
        st.subheader("📋 Historial de Ventas")
        
        ventas_df = pd.read_sql("""
            SELECT v.*, p.codigo, p.nombre 
            FROM ventas v
            JOIN productos p ON v.producto_id = p.id
            ORDER BY v.fecha DESC
        """, conn)
        
        if not ventas_df.empty:
            # Filtros
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                fecha_ini = st.date_input("Desde", ventas_df['fecha'].min() if not ventas_df.empty else datetime.now().date())
            with col_f2:
                fecha_fin = st.date_input("Hasta", ventas_df['fecha'].max() if not ventas_df.empty else datetime.now().date())
            with col_f3:
                metodo_filtro = st.selectbox("Método de Pago", ["Todos"] + ventas_df['metodo_pago'].unique().tolist())
            
            # Aplicar filtros
            ventas_df['fecha'] = pd.to_datetime(ventas_df['fecha']).dt.date
            ventas_filtradas = ventas_df[
                (ventas_df['fecha'] >= fecha_ini) & 
                (ventas_df['fecha'] <= fecha_fin)
            ]
            
            if metodo_filtro != "Todos":
                ventas_filtradas = ventas_filtradas[ventas_filtradas['metodo_pago'] == metodo_filtro]
            
            if not ventas_filtradas.empty:
                # Mostrar resumen
                total_ventas = ventas_filtradas['total_venta'].sum()
                total_unidades = ventas_filtradas['cantidad'].sum()
                
                c1, c2, c3 = st.columns(3)
                c1.metric("💰 Total Ventas", f"{total_ventas:,.2f} €")
                c2.metric("📦 Total Unidades Vendidas", total_unidades)
                c3.metric("📊 Promedio por Venta", f"{(total_ventas/len(ventas_filtradas)):.2f} €" if len(ventas_filtradas) > 0 else "0 €")
                
                # Gráfico de ventas por día
                st.subheader("📈 Ventas Diarias")
                ventas_diarias = ventas_filtradas.groupby('fecha')['total_venta'].sum().reset_index()
                st.line_chart(data=ventas_diarias.set_index('fecha'))
                
                st.dataframe(ventas_filtradas[['fecha', 'codigo', 'nombre', 'cantidad', 'precio_unitario', 'total_venta', 'metodo_pago', 'cliente']], 
                           use_container_width=True)
                
                # Botón para descargar
                csv_data = ventas_filtradas.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')
                st.download_button(
                    label="📥 Descargar Reporte de Ventas", 
                    data=csv_data, 
                    file_name=f"ventas_{fecha_ini}_a_{fecha_fin}.csv", 
                    mime="text/csv"
                )
            else:
                st.info("No hay ventas en el rango de fechas seleccionado.")
        else:
            st.info("Aún no hay registros de ventas.")
    
    conn.close()

# ==========================================
# 📊 BALANCE GENERAL
# ==========================================
elif menu == "📊 Balance General":
    st.subheader("📊 Balance General del Negocio")
    
    conn = conectar_db()
    
    # ====== 1. Resumen de Inventario ======
    st.markdown("### 📦 Resumen de Inventario")
    
    inventario_df = pd.read_sql("""
        SELECT 
            COUNT(*) as total_productos,
            SUM(stock_actual) as total_unidades,
            SUM(stock_actual * precio_compra) as valor_inventario_costo,
            SUM(stock_actual * precio_venta) as valor_inventario_venta
        FROM productos
    """, conn)
    
    if not inventario_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📦 Total Productos", int(inventario_df['total_productos'].iloc[0]))
        col2.metric("📦 Total Unidades", int(inventario_df['total_unidades'].iloc[0]))
        col3.metric("💰 Valor (Costo)", f"{inventario_df['valor_inventario_costo'].iloc[0]:,.2f} €")
        col4.metric("💰 Valor (Venta)", f"{inventario_df['valor_inventario_venta'].iloc[0]:,.2f} €")
    
    # ====== 2. Resumen de Ventas ======
    st.markdown("### 💳 Resumen de Ventas")
    
    # Ventas totales
    ventas_totales = pd.read_sql("""
        SELECT 
            COUNT(*) as total_ventas,
            SUM(cantidad) as total_unidades_vendidas,
            SUM(total_venta) as total_ingresos
        FROM ventas
    """, conn)
    
    # Ventas por período
    hoy = datetime.now().date()
    ventas_hoy = pd.read_sql("""
        SELECT 
            COUNT(*) as ventas_hoy,
            SUM(cantidad) as unidades_hoy,
            SUM(total_venta) as ingresos_hoy
        FROM ventas
        WHERE fecha = %s
    """, conn, params=(hoy,))
    
    # Ventas del mes
    inicio_mes = hoy.replace(day=1)
    ventas_mes = pd.read_sql("""
        SELECT 
            COUNT(*) as ventas_mes,
            SUM(cantidad) as unidades_mes,
            SUM(total_venta) as ingresos_mes
        FROM ventas
        WHERE fecha >= %s
    """, conn, params=(inicio_mes,))
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Ingresos Totales", f"{ventas_totales['total_ingresos'].iloc[0]:,.2f} €" if not ventas_totales.empty else "0 €")
    col2.metric("📈 Ventas Hoy", f"{ventas_hoy['ingresos_hoy'].iloc[0]:,.2f} €" if not ventas_hoy.empty else "0 €")
    col3.metric("📆 Ventas del Mes", f"{ventas_mes['ingresos_mes'].iloc[0]:,.2f} €" if not ventas_mes.empty else "0 €")
    
    # ====== 3. Resumen de Compras ======
    st.markdown("### 📥 Resumen de Compras")
    
    compras_totales = pd.read_sql("""
        SELECT 
            COUNT(*) as total_compras,
            SUM(cantidad) as total_unidades_compradas,
            SUM(total_compra) as total_invertido
        FROM compras
    """, conn)
    
    # Compras del mes
    compras_mes = pd.read_sql("""
        SELECT 
            COUNT(*) as compras_mes,
            SUM(cantidad) as unidades_mes,
            SUM(total_compra) as invertido_mes
        FROM compras
        WHERE fecha >= %s
    """, conn, params=(inicio_mes,))
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total Invertido", f"{compras_totales['total_invertido'].iloc[0]:,.2f} €" if not compras_totales.empty else "0 €")
    col2.metric("📦 Unidades Compradas", int(compras_totales['total_unidades_compradas'].iloc[0]) if not compras_totales.empty else 0)
    col3.metric("📆 Compras del Mes", f"{compras_mes['invertido_mes'].iloc[0]:,.2f} €" if not compras_mes.empty else "0 €")
    
    # ====== 4. Balance ======
    st.markdown("---")
    st.markdown("### 📊 Balance General")
    
    ingresos_totales = ventas_totales['total_ingresos'].iloc[0] if not ventas_totales.empty else 0
    costo_inventario = inventario_df['valor_inventario_costo'].iloc[0] if not inventario_df.empty else 0
    gastos_compras = compras_totales['total_invertido'].iloc[0] if not compras_totales.empty else 0
    
    # Beneficio = Ingresos - Costo de lo vendido
    # Estimamos el costo de lo vendido = valor del inventario inicial - valor del inventario actual + compras
    # Para simplificar: Beneficio = Ingresos - (Compras + Inventario Inicial - Inventario Actual)
    # Suponemos que el inventario inicial se puede calcular como compras anteriores
    
    # Para este cálculo simple: Beneficio = Ingresos - (Compras - Variación de Inventario)
    # Beneficio aproximado = Ingresos - Costo de lo vendido
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 Ingresos Totales", f"{ingresos_totales:,.2f} €")
    col2.metric("🛒 Total Compras", f"{gastos_compras:,.2f} €")
    col3.metric("📦 Valor Inventario", f"{costo_inventario:,.2f} €")
    
    # Beneficio aproximado (simplificado)
    beneficio = ingresos_totales - gastos_compras
    col4.metric("📈 Beneficio Estimado", f"{beneficio:,.2f} €", 
                delta="Positivo" if beneficio > 0 else "Negativo")
    
    # ====== 5. Productos más vendidos ======
    st.markdown("### 🏆 Productos Más Vendidos")
    
    top_productos = pd.read_sql("""
        SELECT 
            p.nombre, 
            p.categoria,
            SUM(v.cantidad) as total_vendido,
            SUM(v.total_venta) as total_ingresos
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        GROUP BY p.nombre, p.categoria
        ORDER BY total_ingresos DESC
        LIMIT 10
    """, conn)
    
    if not top_productos.empty:
        st.dataframe(top_productos, use_container_width=True)
        
        # Gráfico
        st.bar_chart(data=top_productos.set_index('nombre')['total_ingresos'])
    else:
        st.info("Aún no hay datos de ventas.")
    
    # ====== 6. Productos sin stock ======
    st.markdown("### ⚠️ Productos sin Stock")
    
    sin_stock = pd.read_sql("""
        SELECT codigo, nombre, categoria, stock_actual, stock_minimo
        FROM productos
        WHERE stock_actual <= 0
        ORDER BY nombre
    """, conn)
    
    if not sin_stock.empty:
        st.warning(f"{len(sin_stock)} productos agotados")
        st.dataframe(sin_stock, use_container_width=True)
    else:
        st.success("✅ Todos los productos tienen stock disponible.")
    
    conn.close()

# ==========================================
# 🏷️ CATEGORÍAS
# ==========================================
elif menu == "🏷️ Categorías" and st.session_state.u_rol == "admin":
    st.subheader("Gestión de Categorías")
    conn = conectar_db()
    
    tabs = st.tabs(["➕ Nueva Categoría", "✏️ Editar Categoría", "🔍 Ver Categorías"])
    
    with tabs[0]:
        with st.form("form_nueva_categoria"):
            nombre_cat = st.text_input("Nombre de la Categoría")
            if st.form_submit_button("Guardar Categoría"):
                if nombre_cat.strip():
                    cur = conn.cursor()
                    try:
                        cur.execute("INSERT INTO categorias (nombre) VALUES (%s)", (nombre_cat.strip(),))
                        conn.commit()
                        st.success("✅ Categoría agregada")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error("⚠️ Esta categoría ya existe.")
                else:
                    st.warning("El nombre no puede estar vacío.")
    
    with tabs[1]:
        categorias_df = pd.read_sql("SELECT id, nombre FROM categorias ORDER BY nombre", conn)
        if not categorias_df.empty:
            cat_sel = st.selectbox("Seleccionar categoría", categorias_df['nombre'])
            cat_data = categorias_df[categorias_df['nombre'] == cat_sel].iloc[0]
            
            with st.form("form_editar_categoria"):
                nuevo_nombre = st.text_input("Nuevo nombre", value=cat_data['nombre'])
                if st.form_submit_button("Actualizar"):
                    cur = conn.cursor()
                    try:
                        cur.execute("UPDATE categorias SET nombre = %s WHERE id = %s", 
                                   (nuevo_nombre, int(cat_data['id'])))
                        conn.commit()
                        st.success("✅ Categoría actualizada")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error("⚠️ Error: Ya existe otra categoría con ese nombre.")
        else:
            st.info("No hay categorías registradas.")
    
    with tabs[2]:
        categorias_ver = pd.read_sql("SELECT nombre FROM categorias ORDER BY nombre", conn)
        st.dataframe(categorias_ver, use_container_width=True)
    
    conn.close()

# ==========================================
# 👥 USUARIOS
# ==========================================
elif menu == "👥 Usuarios" and st.session_state.u_rol == "admin":
    st.subheader("👥 Gestión de Usuarios")
    conn = conectar_db()
    
    with st.form("form_crear_usuario"):
        st.markdown("### Crear Nuevo Usuario")
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre Completo")
            usuario = st.text_input("Nombre de Usuario *")
        with c2:
            clave = st.text_input("Contraseña *", type="password")
            rol = st.selectbox("Rol", ["vendedor", "admin"])
        
        st.caption("* Campos obligatorios")
        
        if st.form_submit_button("Crear Usuario"):
            if not usuario.strip():
                st.warning("El nombre de usuario es obligatorio.")
            elif not clave.strip():
                st.warning("La contraseña es obligatoria.")
            else:
                cur = conn.cursor()
                try:
                    cur.execute("INSERT INTO usuarios (nombre, usuario, clave, rol) VALUES (%s, %s, %s, %s)",
                               (nombre, usuario, hashlib.sha256(clave.encode()).hexdigest(), rol))
                    conn.commit()
                    st.success("✅ Usuario creado exitosamente")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error("⚠️ Error: Este nombre de usuario ya existe.")
    
    # Lista de usuarios
    st.markdown("### 📋 Usuarios Registrados")
    usuarios_df = pd.read_sql("SELECT id, nombre, usuario, rol FROM usuarios", conn)
    st.dataframe(usuarios_df, use_container_width=True)
    
    conn.close()

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================
elif menu == "⚙️ Configuración" and st.session_state.u_rol == "admin":
    st.subheader("⚙️ Configuración del Sistema")
    conn = conectar_db()
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM configuracion WHERE id = 1")
    config = cur.fetchone()
    
    with st.form("form_configuracion"):
        st.markdown("### Datos del Negocio")
        nombre_neg = st.text_input("Nombre del Negocio", value=config[1] if config else "Mi Negocio")
        direccion = st.text_input("Dirección", value=config[2] if config and len(config) > 2 else "")
        telefono = st.text_input("Teléfono", value=config[3] if config and len(config) > 3 else "")
        email = st.text_input("Email", value=config[4] if config and len(config) > 4 else "")
        moneda = st.text_input("Símbolo de Moneda", value=config[5] if config and len(config) > 5 else "€")
        iva = st.number_input("IVA (%)", min_value=0.0, max_value=100.0, value=float(config[6]) if config and len(config) > 6 else 0.0)
        
        if st.form_submit_button("💾 Guardar Configuración"):
            try:
                cur.execute("""
                    INSERT INTO configuracion (id, nombre_negocio, direccion, telefono, email, moneda, iva)
                    VALUES (1, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        nombre_negocio = EXCLUDED.nombre_negocio,
                        direccion = EXCLUDED.direccion,
                        telefono = EXCLUDED.telefono,
                        email = EXCLUDED.email,
                        moneda = EXCLUDED.moneda,
                        iva = EXCLUDED.iva
                """, (nombre_neg, direccion, telefono, email, moneda, iva))
                conn.commit()
                st.success("✅ Configuración guardada")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.error(f"⚠️ Error: {e}")
    
    conn.close()

# ==========================================
# EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    st.markdown("---")
    st.caption("📦 Sistema de Inventario y Ventas v1.0")
