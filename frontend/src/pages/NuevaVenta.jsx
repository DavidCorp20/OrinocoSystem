import Stock from "./Stock";

/**
 * Punto de venta principal de CuadraApp.
 * Mantiene el catálogo/carrito compartido con Stock, pero se expone como
 * una pantalla comercial independiente para vendedores y administradores.
 */
export default function NuevaVenta(){
  return <Stock mode="sale" />;
}
