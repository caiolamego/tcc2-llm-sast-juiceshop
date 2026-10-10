async function vulnerable(collection, id) {
  const item = await collection.findOne({ _id: id });
  if (item.users.includes(user)) return;
  // ruleid: tcc.concurrency.security.delayed-counter-update
  await collection.update({ _id: id }, { $inc: { count: 1 } });
  await delay(100);
  await collection.update({ _id: id }, { $set: { users: [...item.users, user] } });
}
async function protectedUpdate(collection, id) {
  // ok: tcc.concurrency.security.delayed-counter-update
  await collection.update({ _id: id, users: { $ne: user } }, { $inc: { count: 1 }, $addToSet: { users: user } });
}
async function externalLock(collection, id) {
  await lock(id);
  // Falso positivo conhecido: lock externo cobre operacoes seguintes.
  // ruleid: tcc.concurrency.security.delayed-counter-update
  await collection.update({ _id: id }, { $inc: { count: 1 } });
  await delay(100);
  await unlock(id);
}
