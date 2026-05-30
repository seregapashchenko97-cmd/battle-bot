async def main():
    print("STEP 1")

    me = await bot.get_me()
    print("STEP 2")

    print("BOT ID:", me.id)
    print("BOT USERNAME:", me.username)

    print("STEP 3")
    await bot.delete_webhook(drop_pending_updates=True)

    print("STEP 4")
    await dp.start_polling(bot)

    print("STEP 5")
