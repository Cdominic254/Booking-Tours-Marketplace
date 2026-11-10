import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three/src/Three.js';

function createHull() {
  const sections = [
    [-1.4, 0.02, 0.08],
    [-1.12, 0.3, 0.04],
    [-0.62, 0.47, 0.02],
    [0.2, 0.46, 0.04],
    [0.92, 0.32, 0.08],
    [1.36, 0.06, 0.13],
  ];
  const sectionPoints = sections.map(([z, width, top]) => [
    [width, top, z],
    [width * 0.82, -0.13, z],
    [0, -0.32, z],
    [-width * 0.82, -0.13, z],
    [-width, top, z],
  ]);
  const positions = [];
  const indices = [];

  sectionPoints.forEach((section) => section.forEach((point) => positions.push(...point)));
  for (let section = 0; section < sectionPoints.length - 1; section += 1) {
    for (let edge = 0; edge < 4; edge += 1) {
      const current = section * 5 + edge;
      const next = current + 5;
      indices.push(current, current + 1, next, current + 1, next + 1, next);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function createSail() {
  const mastBase = new THREE.Vector3(-0.15, 0.23, -0.24);
  const mastTop = new THREE.Vector3(-0.15, 2.35, -0.24);
  const boomEnd = new THREE.Vector3(1.48, 0.3, -0.24);
  const divisions = 18;
  const positions = [];
  const indices = [];
  const rows = [];

  for (let row = 0; row <= divisions; row += 1) {
    const pointsInRow = divisions - row + 1;
    rows.push(pointsInRow);
    for (let column = 0; column < pointsInRow; column += 1) {
      const alongMast = row / divisions;
      const alongBoom = column / divisions;
      const point = mastBase.clone()
        .multiplyScalar(1 - alongMast - alongBoom)
        .addScaledVector(mastTop, alongMast)
        .addScaledVector(boomEnd, alongBoom);
      point.z += 0.12 * Math.sin(Math.PI * (alongMast + alongBoom));
      positions.push(point.x, point.y, point.z);
    }
  }

  const rowStarts = [];
  rows.forEach((length, index) => {
    rowStarts[index] = rows.slice(0, index).reduce((sum, value) => sum + value, 0);
    for (let column = 0; column < length - 1; column += 1) {
      const topLeft = rowStarts[index] + column;
      const topRight = topLeft + 1;
      const bottomLeft = rowStarts[index + 1] + column;
      indices.push(topLeft, bottomLeft, topRight);
      if (column < length - 2) indices.push(topRight, bottomLeft, bottomLeft + 1);
    }
  });

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

function addRod(group, start, end, radius, material, radialSegments = 8) {
  const direction = new THREE.Vector3().subVectors(end, start);
  const mesh = new THREE.Mesh(
    new THREE.CylinderGeometry(radius, radius, direction.length(), radialSegments),
    material,
  );
  mesh.position.copy(start).add(end).multiplyScalar(0.5);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
  group.add(mesh);
}

function createDhow(scene) {
  const boat = new THREE.Group();
  const wood = new THREE.MeshStandardMaterial({ color: '#75412d', roughness: 0.7, metalness: 0.04, side: THREE.DoubleSide });
  const deckWood = new THREE.MeshStandardMaterial({ color: '#c18a57', roughness: 0.78, side: THREE.DoubleSide });
  const mastWood = new THREE.MeshStandardMaterial({ color: '#483024', roughness: 0.8 });
  const sailFabric = new THREE.MeshStandardMaterial({
    color: '#f4e5c4',
    roughness: 0.9,
    side: THREE.DoubleSide,
    transparent: true,
    opacity: 0.96,
  });
  const ropeMaterial = new THREE.MeshStandardMaterial({ color: '#d3b88a', roughness: 0.9 });
  const hull = new THREE.Mesh(createHull(), wood);
  hull.castShadow = true;
  hull.receiveShadow = true;
  boat.add(hull);

  const deckGeometry = new THREE.BufferGeometry();
  const deckPositions = [];
  const deckIndices = [];
  const stations = [
    [-1.33, 0.04],
    [-1.08, 0.3],
    [-0.62, 0.45],
    [0.2, 0.44],
    [0.9, 0.31],
    [1.32, 0.07],
  ];
  stations.forEach(([z, width], index) => {
    deckPositions.push(-width, 0.045, z, width, 0.045, z);
    if (index < stations.length - 1) {
      const left = index * 2;
      deckIndices.push(left, left + 1, left + 2, left + 1, left + 3, left + 2);
    }
  });
  deckGeometry.setAttribute('position', new THREE.Float32BufferAttribute(deckPositions, 3));
  deckGeometry.setIndex(deckIndices);
  deckGeometry.computeVertexNormals();
  boat.add(new THREE.Mesh(deckGeometry, deckWood));

  const mastBase = new THREE.Vector3(-0.15, 0.08, -0.24);
  const mastTop = new THREE.Vector3(-0.15, 2.38, -0.24);
  const boomStart = new THREE.Vector3(-0.15, 0.25, -0.24);
  const boomEnd = new THREE.Vector3(1.48, 0.3, -0.24);
  addRod(boat, mastBase, mastTop, 0.035, mastWood, 10);
  addRod(boat, boomStart, boomEnd, 0.024, mastWood, 8);

  const sail = new THREE.Mesh(createSail(), sailFabric);
  sail.castShadow = true;
  boat.add(sail);

  const sailSeams = new THREE.Group();
  const seamMaterial = new THREE.MeshStandardMaterial({ color: '#d6c6a9', roughness: 0.9 });
  for (let index = 1; index <= 5; index += 1) {
    const point = index / 6;
    const start = new THREE.Vector3(-0.15 + point * 1.63, 0.3 + point * 2.05, -0.1);
    const end = new THREE.Vector3(-0.15 + point * 1.63, 0.3, -0.1);
    addRod(sailSeams, start, end, 0.004, seamMaterial, 4);
  }
  boat.add(sailSeams);

  const riggingPoints = [
    [mastTop, new THREE.Vector3(0.43, 0.07, 0.12)],
    [mastTop, new THREE.Vector3(-0.35, 0.07, 0.15)],
    [mastTop, boomEnd],
  ];
  riggingPoints.forEach(([start, end]) => addRod(boat, start, end, 0.008, ropeMaterial, 4));

  for (let index = 0; index < 6; index += 1) {
    const z = -0.95 + index * 0.33;
    const width = z < -0.62 ? 0.29 : 0.43;
    addRod(
      boat,
      new THREE.Vector3(-width, 0.065, z),
      new THREE.Vector3(width, 0.065, z),
      0.012,
      deckWood,
      5,
    );
  }

  boat.scale.setScalar(0.78);
  boat.position.y = -0.1;
  boat.rotation.y = -0.16;
  scene.add(boat);

  const rippleMaterial = new THREE.MeshBasicMaterial({ color: '#b8eff4', transparent: true, opacity: 0.3 });
  const ripples = [1.1, 1.4, 1.7].map((radius, index) => {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(radius, 0.006, 6, 72), rippleMaterial.clone());
    ring.rotation.x = Math.PI / 2;
    ring.position.set(0, -0.34 - index * 0.008, 0);
    scene.add(ring);
    return ring;
  });

  return { boat, ripples, materials: [wood, deckWood, mastWood, sailFabric, ropeMaterial, seamMaterial, rippleMaterial] };
}

export default function DhowModel() {
  const stageRef = useRef(null);
  const [desktopScene, setDesktopScene] = useState(() => window.matchMedia('(min-width: 900px)').matches);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const media = window.matchMedia('(min-width: 900px)');
    const updateViewport = () => setDesktopScene(media.matches);
    media.addEventListener('change', updateViewport);
    return () => media.removeEventListener('change', updateViewport);
  }, []);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !desktopScene || unavailable) return undefined;

    let renderer;
    let model;
    let resizeObserver;
    let intersectionObserver;
    let frameTime = 0;
    let stageVisible = false;
    let pointerDown = false;
    let previousPointer = { x: 0, y: 0 };
    const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
    let reducedMotion = motionPreference.matches;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 100);
    camera.position.set(4.3, 3, 5.8);
    camera.lookAt(0, 0.62, 0);
    scene.add(new THREE.HemisphereLight('#e9fbff', '#31536a', 2.4));

    const sun = new THREE.DirectionalLight('#fff1d4', 3.2);
    sun.position.set(-3, 6, 5);
    scene.add(sun);
    const fill = new THREE.DirectionalLight('#7ee2e1', 1.35);
    fill.position.set(4, 2.5, -4);
    scene.add(fill);

    try {
      renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
      renderer.setSize(stage.clientWidth, stage.clientHeight);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.12;
      stage.appendChild(renderer.domElement);
      model = createDhow(scene);
    } catch (error) {
      console.error('The interactive dhow preview could not be initialized.', error);
      setUnavailable(true);
      return undefined;
    }

    const renderFrame = (time) => {
      if (document.visibilityState !== 'visible') return;
      if (time - frameTime < 1000 / 30) return;
      frameTime = time;
      const seconds = time / 1000;
      if (!reducedMotion) {
        model.boat.position.y = -0.1 + Math.sin(seconds * 0.8) * 0.035;
        model.boat.rotation.z = Math.sin(seconds * 0.5) * 0.012;
        model.ripples.forEach((ripple, index) => {
          ripple.scale.setScalar(1 + Math.sin(seconds * 0.75 + index) * 0.025);
        });
      }
      renderer.render(scene, camera);
    };

    const resize = () => {
      const { width, height } = stage.getBoundingClientRect();
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
      renderer.render(scene, camera);
    };
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(stage);
    intersectionObserver = new IntersectionObserver(([entry]) => {
      stageVisible = entry.isIntersecting;
      if (entry.isIntersecting && !reducedMotion) renderer.setAnimationLoop(renderFrame);
      else renderer.setAnimationLoop(null);
      if (entry.isIntersecting && reducedMotion) renderer.render(scene, camera);
    });
    intersectionObserver.observe(stage);

    const updateMotionPreference = (event) => {
      reducedMotion = event.matches;
      if (!stageVisible || reducedMotion) {
        renderer.setAnimationLoop(null);
        if (stageVisible) renderer.render(scene, camera);
      } else {
        frameTime = 0;
        renderer.setAnimationLoop(renderFrame);
      }
    };
    motionPreference.addEventListener('change', updateMotionPreference);

    const canvas = renderer.domElement;
    const pointerStart = (event) => {
      pointerDown = true;
      previousPointer = { x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
      canvas.classList.add('is-dragging');
    };
    const pointerMove = (event) => {
      if (!pointerDown) return;
      const deltaX = event.clientX - previousPointer.x;
      const deltaY = event.clientY - previousPointer.y;
      previousPointer = { x: event.clientX, y: event.clientY };
      model.boat.rotation.y += deltaX * 0.008;
      model.boat.rotation.x = THREE.MathUtils.clamp(model.boat.rotation.x + deltaY * 0.003, -0.16, 0.16);
      if (reducedMotion) renderer.render(scene, camera);
    };
    const pointerEnd = () => {
      pointerDown = false;
      canvas.classList.remove('is-dragging');
    };
    canvas.addEventListener('pointerdown', pointerStart);
    canvas.addEventListener('pointermove', pointerMove);
    canvas.addEventListener('pointerup', pointerEnd);
    canvas.addEventListener('pointercancel', pointerEnd);
    renderer.render(scene, camera);

    return () => {
      renderer.setAnimationLoop(null);
      motionPreference.removeEventListener('change', updateMotionPreference);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      canvas.removeEventListener('pointerdown', pointerStart);
      canvas.removeEventListener('pointermove', pointerMove);
      canvas.removeEventListener('pointerup', pointerEnd);
      canvas.removeEventListener('pointercancel', pointerEnd);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) object.geometry.dispose();
      });
      model.materials.forEach((material) => material.dispose());
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh && Array.isArray(object.material) === false
          && !model.materials.includes(object.material)) object.material.dispose();
      });
      renderer.dispose();
      canvas.remove();
    };
  }, [desktopScene, unavailable]);

  return (
    <div
      className={`dhow-stage ${desktopScene ? '' : 'dhow-stage--static'}`}
      ref={stageRef}
      role="img"
      aria-label="Interactive 3D model of a traditional Kenyan dhow. Drag to turn the boat."
    >
      {(!desktopScene || unavailable) && <img src="/images/IMG_2026-03-23-17-36-36-712.jpg" alt="Traditional dhow boats on the water off the Kenyan coast" />}
      {desktopScene && !unavailable && <span className="dhow-model-hint" aria-hidden="true">Drag to explore the dhow</span>}
    </div>
  );
}
